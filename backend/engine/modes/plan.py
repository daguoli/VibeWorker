"""PlanMode — Phase 2 计划执行，独立子 Agent + Replanner。

每个步骤使用独立的 Executor 子 Agent（防止上下文膨胀）。
每步执行后，Replanner 评估是否继续、修订或完成。
"""
import logging
from typing import Optional

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field

from config import settings
from engine.context import RunContext
from engine import events
from engine.llm_factory import get_llm
from engine.stream_adapter import stream_agent_events
from prompt_builder import build_system_prompt
from tools import get_executor_tools
from tools.plan_tool import send_plan_updated_event, send_plan_revised_event

logger = logging.getLogger(__name__)


class ReplanDecision(BaseModel):
    """Replanner LLM 的结构化输出。"""
    action: str = Field(description="决策动作: continue / revise / finish")
    response: str = Field(default="", description="当 action=finish 时的最终回复")
    revised_steps: list[str] = Field(default_factory=list, description="当 action=revise 时的新步骤列表")
    reason: str = Field(default="", description="决策原因")


class PlanMode:
    """Phase 2：逐步执行计划，带 Replanner 评估。"""

    def __init__(self, plan_data: dict, original_messages: list):
        self.plan_data = plan_data
        self.original_messages = original_messages

    async def execute(self, ctx: RunContext):
        plan_id = self.plan_data["plan_id"]
        plan_title = self.plan_data["title"]
        steps = list(self.plan_data["steps"])  # 创建可变副本
        system_prompt = build_system_prompt()

        past_steps: list[tuple[str, str]] = []
        step_index = 0

        while step_index < len(steps) and step_index < settings.plan_max_steps:
            step = steps[step_index]
            step_title = step["title"] if isinstance(step, dict) else str(step)
            step_id = step["id"] if isinstance(step, dict) else step_index + 1

            # 标记步骤为运行中
            send_plan_updated_event(plan_id, step_id, "running")

            # 构建带历史上下文的 Executor 提示
            executor_prompt = self._build_executor_prompt(
                system_prompt, plan_title, step_title, step_index, len(steps), past_steps
            )

            executor_llm = get_llm(streaming=True)
            executor_tools = get_executor_tools()
            sub_agent = create_react_agent(
                model=executor_llm, tools=executor_tools, prompt=executor_prompt
            )

            input_messages = list(self.original_messages)
            input_messages.append(HumanMessage(content=f"执行步骤 {step_index + 1}: {step_title}"))

            sub_config = {"recursion_limit": 30}
            step_response = ""

            # 执行步骤（带错误恢复）
            try:
                async for event in stream_agent_events(
                    sub_agent, {"messages": input_messages}, sub_config,
                    system_prompt=system_prompt,
                    node_label="executor",
                    motivation=f"执行步骤 {step_index + 1}: {step_title}",
                    instruction=executor_prompt,
                ):
                    if event.get("type") == events.TOKEN:
                        step_response += event.get("content", "")
                    yield event

                send_plan_updated_event(plan_id, step_id, "completed")
            except Exception as e:
                send_plan_updated_event(plan_id, step_id, "failed")
                yield events.build_token(f"\n\n> 步骤 {step_index + 1} 执行失败: {e}\n")
                step_response = f"[ERROR] {e}"
                logger.error(f"步骤 {step_index + 1} 执行失败: {e}", exc_info=True)

            past_steps.append((step_title, step_response[:1000]))
            step_index += 1

            # Replanner 评估
            remaining = len(steps) - step_index
            if remaining > 0:
                decision = await self._evaluate_replan(
                    plan_title, steps, past_steps, step_index, system_prompt
                )

                if decision:
                    if decision.action == "finish":
                        # 将剩余步骤标记为已完成（跳过）
                        for i in range(step_index, len(steps)):
                            s = steps[i]
                            sid = s["id"] if isinstance(s, dict) else i + 1
                            send_plan_updated_event(plan_id, sid, "completed")

                        if decision.response:
                            yield events.build_token("\n\n" + decision.response)
                        break

                    elif decision.action == "revise" and decision.revised_steps:
                        new_steps = [
                            {"id": step_index + i + 1, "title": s.strip(), "status": "pending"}
                            for i, s in enumerate(decision.revised_steps)
                        ]
                        send_plan_revised_event(plan_id, new_steps, step_index, decision.reason)
                        steps = steps[:step_index] + new_steps

        yield events.build_done()

    def _build_executor_prompt(self, system_prompt, plan_title, step_title,
                                step_index, total_steps, past_steps):
        past_context = ""
        if past_steps:
            past_context = "\n".join(
                f"步骤 {i+1} [{s}]: {r[:300]}" for i, (s, r) in enumerate(past_steps)
            )

        return f"""{system_prompt}

计划标题：{plan_title}
当前步骤（{step_index + 1}/{total_steps}）：{step_title}

{f'已完成的步骤：{chr(10)}{past_context}' if past_context else ''}

请专注完成当前步骤。完成后简要总结结果。"""

    # ---------- Replanner ----------

    async def _evaluate_replan(self, plan_title, steps, past_steps,
                                current_index, system_prompt) -> Optional[ReplanDecision]:
        if not settings.plan_revision_enabled:
            return None

        remaining_steps = steps[current_index:]
        if not remaining_steps:
            return None

        # 启发式预检：常规情况下跳过 LLM 调用
        if self._should_skip_replan(past_steps, current_index, len(steps)):
            return None

        past_str = "\n".join(
            f"步骤 {i+1} [{s}]: {r[:200]}" for i, (s, r) in enumerate(past_steps)
        )
        remaining_str = "\n".join(
            f"步骤 {(s['id'] if isinstance(s, dict) else current_index + i + 1)}: "
            f"{(s['title'] if isinstance(s, dict) else str(s))}"
            for i, s in enumerate(remaining_steps)
        )

        replan_prompt = f"""你是一个计划评估专家。请根据当前执行进度评估是否需要调整计划。

计划标题：{plan_title}

已完成的步骤：
{past_str}

剩余步骤：
{remaining_str}

请选择一个动作：
- **continue**: 剩余步骤合理，继续执行下一步
- **revise**: 根据已完成步骤的结果，需要修改剩余步骤
- **finish**: 任务目标已经达成，无需继续执行剩余步骤

请以 JSON 格式回复。"""

        try:
            llm = get_llm(streaming=False)
            structured_llm = llm.with_structured_output(ReplanDecision)
            decision = await structured_llm.ainvoke(replan_prompt)
            logger.info(f"[REPLANNER] 决策: {decision.action} - {decision.reason}")
            return decision
        except Exception as e:
            logger.warning(f"[REPLANNER] 评估失败，降级为继续执行: {e}")
            return None

    def _should_skip_replan(self, past_steps, step_index, total) -> bool:
        """启发式预检：常规情况下跳过 LLM Replan 调用。"""
        # 仅剩 1 步 → 无需重规划
        if total - step_index <= 1:
            return True
        # 最后一步执行成功（无错误） → 正常继续
        if past_steps:
            last_response = past_steps[-1][1]
            if "[ERROR]" not in last_response:
                return True
        return False
