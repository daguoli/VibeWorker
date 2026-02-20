"use client";

import React, { useState, useMemo } from "react";
import { ChevronRight, ChevronDown, List, FileText, Copy, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * 解析 LLM debug input，支持树状折叠展示和原始文本切换。
 *
 * 输入格式示例：
 * [System Prompt]
 * <!-- SKILLS_SNAPSHOT -->
 * ...内容...
 * <!-- SOUL -->
 * ...内容...
 *
 * [Messages]
 * [HumanMessage]
 * 用户消息...
 * ---
 * [AIMessage]
 * AI回复...
 */

interface Section {
  label: string;        // 段落标签
  content: string;      // 段落内容
  charCount: number;    // 字符数
  children?: Section[]; // 子段落
}

// 解析 <!-- XXX --> 注释，提取 System Prompt 内的子段落
function parseSystemPromptSections(content: string): Section[] {
  const sections: Section[] = [];
  // 匹配 <!-- XXX --> 格式的注释作为分隔符（支持大小写和下划线）
  const regex = /<!--\s*([A-Za-z_]+)\s*-->/g;
  const matches = [...content.matchAll(regex)];

  if (matches.length === 0) {
    return [{
      label: "Content",
      content: content.trim(),
      charCount: content.trim().length,
    }];
  }

  // 处理第一个标记之前的内容
  const firstMatchIndex = matches[0].index!;
  if (firstMatchIndex > 0) {
    const beforeContent = content.slice(0, firstMatchIndex).trim();
    if (beforeContent) {
      sections.push({
        label: "Preamble",
        content: beforeContent,
        charCount: beforeContent.length,
      });
    }
  }

  // 按标记分割内容
  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    const label = match[1];
    const startIndex = match.index! + match[0].length;
    const endIndex = i < matches.length - 1 ? matches[i + 1].index! : content.length;
    const sectionContent = content.slice(startIndex, endIndex).trim();
    // 移除段落之间的分隔线 "---"
    const cleanContent = sectionContent.replace(/^\s*---\s*$/gm, "").trim();

    sections.push({
      label,
      content: cleanContent,
      charCount: cleanContent.length,
    });
  }

  return sections;
}

// 解析消息列表：[SystemMessage], [HumanMessage], [AIMessage] 等
function parseTopLevelSections(input: string): Section[] {
  const sections: Section[] = [];
  // 匹配 [XXXMessage] 格式
  const regex = /\[(\w+Message)\]\s*\n/g;
  const matches = [...input.matchAll(regex)];

  if (matches.length === 0) {
    // 没有找到消息标记，作为单个段落返回
    return [{
      label: "Input",
      content: input.trim(),
      charCount: input.trim().length,
    }];
  }

  for (let i = 0; i < matches.length; i++) {
    const match = matches[i];
    const label = match[1];
    const startIndex = match.index! + match[0].length;
    const endIndex = i < matches.length - 1 ? matches[i + 1].index! : input.length;
    let sectionContent = input.slice(startIndex, endIndex).trim();
    // 移除末尾的分隔线 "---"
    sectionContent = sectionContent.replace(/\n---\s*$/, "").trim();

    const section: Section = {
      label,
      content: sectionContent,
      charCount: sectionContent.length,
    };

    // SystemMessage 内部按 <!-- --> 分段（包含 SKILLS_SNAPSHOT、SOUL 等）
    if (label === "SystemMessage") {
      section.children = parseSystemPromptSections(sectionContent);
    }

    sections.push(section);
  }

  return sections;
}

// 格式化字符数显示
function formatCharCount(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

// 单个段落组件
interface SectionItemProps {
  section: Section;
  defaultExpanded?: boolean;
  depth?: number;
}

function SectionItem({ section, defaultExpanded = false, depth = 0 }: SectionItemProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [copied, setCopied] = useState(false);

  const hasChildren = section.children && section.children.length > 0;
  const indent = depth * 12;

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(section.content).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  // 标签颜色映射
  const labelColorMap: Record<string, string> = {
    // 顶层
    "System Prompt": "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300",
    "Messages": "bg-green-100 dark:bg-green-950 text-green-700 dark:text-green-300",
    "Instruction": "bg-orange-100 dark:bg-orange-950 text-orange-700 dark:text-orange-300",
    // System Prompt 子段落
    "SKILLS_SNAPSHOT": "bg-purple-100 dark:bg-purple-950 text-purple-700 dark:text-purple-300",
    "SOUL": "bg-pink-100 dark:bg-pink-950 text-pink-700 dark:text-pink-300",
    "IDENTITY": "bg-cyan-100 dark:bg-cyan-950 text-cyan-700 dark:text-cyan-300",
    "USER": "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300",
    "AGENTS": "bg-indigo-100 dark:bg-indigo-950 text-indigo-700 dark:text-indigo-300",
    "MEMORY": "bg-rose-100 dark:bg-rose-950 text-rose-700 dark:text-rose-300",
    "DAILY_LOGS": "bg-teal-100 dark:bg-teal-950 text-teal-700 dark:text-teal-300",
    "WORKSPACE_INFO": "bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300",
    // Messages 子段落
    "HumanMessage": "bg-emerald-100 dark:bg-emerald-950 text-emerald-700 dark:text-emerald-300",
    "AIMessage": "bg-violet-100 dark:bg-violet-950 text-violet-700 dark:text-violet-300",
    "SystemMessage": "bg-blue-100 dark:bg-blue-950 text-blue-700 dark:text-blue-300",
    "ToolMessage": "bg-amber-100 dark:bg-amber-950 text-amber-700 dark:text-amber-300",
  };

  const labelClass = labelColorMap[section.label] || "bg-muted text-muted-foreground";

  return (
    <div style={{ marginLeft: indent }}>
      <div
        className="w-full flex items-center gap-1.5 py-1 text-left hover:bg-muted/30 rounded transition-colors group cursor-pointer select-none"
        onClick={() => setExpanded(!expanded)}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setExpanded(!expanded); }}
      >
        <span className="shrink-0 w-4">
          {expanded ? (
            <ChevronDown className="w-3 h-3 text-muted-foreground" />
          ) : (
            <ChevronRight className="w-3 h-3 text-muted-foreground" />
          )}
        </span>
        <span className={`text-[10px] px-1.5 py-0.5 rounded font-mono ${labelClass}`}>
          {section.label}
        </span>
        <span className="text-[10px] text-muted-foreground/60">
          ({formatCharCount(section.charCount)} chars)
        </span>
        <button
          type="button"
          className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity p-0.5"
          onClick={handleCopy}
          title="复制内容"
        >
          {copied ? (
            <Check className="w-3 h-3 text-green-500" />
          ) : (
            <Copy className="w-3 h-3 text-muted-foreground" />
          )}
        </button>
      </div>

      {expanded && (
        <div className="mt-1">
          {hasChildren ? (
            <div className="space-y-0.5">
              {section.children!.map((child, index) => (
                <SectionItem
                  key={index}
                  section={child}
                  depth={depth + 1}
                />
              ))}
            </div>
          ) : (
            <pre
              className="text-[11px] font-mono whitespace-pre-wrap break-all bg-muted/30 rounded-md p-2 max-h-[300px] overflow-auto text-foreground/80"
              style={{ marginLeft: indent + 16 }}
            >
              {section.content || "(empty)"}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}

// 主组件
interface CollapsibleInputProps {
  input: string;
  className?: string;
}

export default function CollapsibleInput({ input, className = "" }: CollapsibleInputProps) {
  // 视图模式：tree（树状） / raw（原始文本）
  const [viewMode, setViewMode] = useState<"tree" | "raw">("tree");
  const [copied, setCopied] = useState(false);

  const sections = useMemo(() => parseTopLevelSections(input), [input]);

  const handleCopyAll = () => {
    navigator.clipboard.writeText(input).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    });
  };

  const toggleViewMode = () => {
    setViewMode(viewMode === "tree" ? "raw" : "tree");
  };

  return (
    <div className={className}>
      {/* 头部：总字符数 + 视图切换按钮 */}
      <div className="flex items-center justify-between mb-1.5">
        <div className="text-[10px] font-medium text-muted-foreground/70 uppercase tracking-wider">
          Input ({formatCharCount(input.length)} chars)
        </div>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            className="w-5 h-5"
            onClick={handleCopyAll}
            title="复制全部"
          >
            {copied ? (
              <Check className="w-3 h-3 text-green-500" />
            ) : (
              <Copy className="w-3 h-3" />
            )}
          </Button>
          <Button
            variant="ghost"
            size="icon"
            className={`w-5 h-5 ${viewMode === "raw" ? "bg-muted" : ""}`}
            onClick={toggleViewMode}
            title={viewMode === "tree" ? "切换到原始文本" : "切换到树状视图"}
          >
            {viewMode === "tree" ? (
              <FileText className="w-3 h-3" />
            ) : (
              <List className="w-3 h-3" />
            )}
          </Button>
        </div>
      </div>

      {/* 内容区域 */}
      {viewMode === "tree" ? (
        <div className="bg-muted/20 rounded-md p-2 space-y-0.5 max-h-[500px] overflow-auto">
          {sections.map((section, index) => (
            <SectionItem
              key={index}
              section={section}
              defaultExpanded={false}
            />
          ))}
        </div>
      ) : (
        <pre className="text-[11px] font-mono whitespace-pre-wrap break-all bg-muted/30 rounded-md p-2 max-h-[500px] overflow-auto text-foreground/80">
          {input || "(empty)"}
        </pre>
      )}
    </div>
  );
}
