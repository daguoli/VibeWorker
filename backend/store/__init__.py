"""Skills Store Module - Integrate with skills.sh ecosystem."""
import json
import logging
import time
import re
import shutil
from pathlib import Path
from typing import Optional

import httpx

from .models import RemoteSkill, SkillDetail, StoreIndexResponse

logger = logging.getLogger("vibeworker.store")

# skills.sh 数据源
SKILLS_SH_URL = "https://skills.sh/"
GITHUB_RAW_BASE = "https://raw.githubusercontent.com"


class SkillsStore:
    """Manages interaction with skills.sh ecosystem."""

    def __init__(
        self,
        skills_dir: Path,
        cache_ttl: int = 3600,
    ):
        self.skills_dir = skills_dir
        self.cache_ttl = cache_ttl
        self._cache: Optional[list] = None
        self._cache_time: float = 0

    def _is_cache_valid(self) -> bool:
        """Check if cached data is still valid."""
        if self._cache is None:
            return False
        return (time.time() - self._cache_time) < self.cache_ttl

    async def _fetch_skills_sh(self) -> list[dict]:
        """Fetch skill list from skills.sh page."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(SKILLS_SH_URL)
                response.raise_for_status()
                html = response.text

                # Extract JSON data from HTML (skills are embedded in the page)
                # Data is escaped with \" in the HTML, so we need to handle that
                pattern = r'\{\\"source\\":\\"([^"\\]+)\\",\\"skillId\\":\\"([^"\\]+)\\",\\"name\\":\\"([^"\\]+)\\",\\"installs\\":(\d+)\}'
                matches = re.findall(pattern, html)

                skills = []
                seen = set()  # Avoid duplicates
                for match in matches:
                    source, skill_id, name, installs = match
                    if skill_id not in seen:
                        seen.add(skill_id)
                        skills.append({
                            "source": source,
                            "skillId": skill_id,
                            "name": name,
                            "installs": int(installs),
                        })

                logger.info(f"Fetched {len(skills)} skills from skills.sh")
                return skills
        except Exception as e:
            logger.error(f"Failed to fetch from skills.sh: {e}")
            return []

    async def fetch_index(self, force_refresh: bool = False) -> list[dict]:
        """Fetch skills index from skills.sh."""
        if not force_refresh and self._is_cache_valid():
            return self._cache

        skills = await self._fetch_skills_sh()

        if skills:
            self._cache = skills
            self._cache_time = time.time()
            return self._cache

        # Return expired cache if nothing else works
        if self._cache is not None:
            logger.warning("Using expired cache")
            return self._cache

        raise RuntimeError("Failed to fetch skills: no source available")

    def _get_installed_skills(self) -> set[str]:
        """Get set of locally installed skill names."""
        installed = set()
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir() and (skill_dir / "SKILL.md").exists():
                    installed.add(skill_dir.name)
        return installed

    def _convert_to_remote_skill(self, s: dict, installed: set[str]) -> RemoteSkill:
        """Convert raw skill data to RemoteSkill model."""
        source = s.get("source", "")
        skill_id = s.get("skillId") or s.get("name", "")
        name = s.get("name", skill_id)
        installs = s.get("installs", 0)

        # Extract author from source (owner/repo -> owner)
        author = source.split("/")[0] if "/" in source else "Unknown"

        # Infer category from source/name
        category = self._infer_category(source, name)

        return RemoteSkill(
            name=name,
            version="1.0.0",
            description=f"Skill from {source}",
            author=author,
            category=category,
            tags=self._infer_tags(name, source),
            downloads=installs,
            rating=min(5.0, 3.0 + (installs / 50000)),  # Estimate rating from installs
            is_installed=name in installed,
        )

    def _infer_category(self, source: str, name: str) -> str:
        """Infer skill category from source and name."""
        name_lower = name.lower()

        if any(x in name_lower for x in ["react", "vue", "frontend", "ui", "design", "css"]):
            return "web"
        if any(x in name_lower for x in ["supabase", "postgres", "database", "sql"]):
            return "data"
        if any(x in name_lower for x in ["browser", "scrape", "fetch"]):
            return "web"
        if any(x in name_lower for x in ["seo", "marketing", "audit"]):
            return "automation"
        if any(x in source.lower() for x in ["vercel", "anthropic"]):
            return "utility"
        return "other"

    def _infer_tags(self, name: str, source: str) -> list[str]:
        """Infer tags from skill name and source."""
        tags = []
        name_lower = name.lower()

        if "react" in name_lower:
            tags.append("react")
        if "vercel" in name_lower or "vercel" in source.lower():
            tags.append("vercel")
        if "design" in name_lower:
            tags.append("design")
        if "browser" in name_lower:
            tags.append("browser")
        if "pdf" in name_lower:
            tags.append("pdf")
        if "supabase" in source.lower():
            tags.append("supabase")

        # Add source as tag
        if "/" in source:
            tags.append(source.split("/")[0])

        return tags[:5]  # Limit to 5 tags

    async def list_remote_skills(
        self,
        category: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> StoreIndexResponse:
        """List available skills."""
        raw_skills = await self.fetch_index()
        installed = self._get_installed_skills()

        # Convert to RemoteSkill objects
        skills = [self._convert_to_remote_skill(s, installed) for s in raw_skills]

        # Filter by category
        if category:
            skills = [s for s in skills if s.category == category]

        # Pagination
        total = len(skills)
        start = (page - 1) * page_size
        end = start + page_size
        skills = skills[start:end]

        return StoreIndexResponse(
            version="1.0.0",
            total=total,
            skills=skills,
        )

    async def search_skills(self, query: str) -> list[RemoteSkill]:
        """Search skills by name or source."""
        raw_skills = await self.fetch_index()
        installed = self._get_installed_skills()
        query_lower = query.lower()

        results = []
        for s in raw_skills:
            name = (s.get("name") or s.get("skillId", "")).lower()
            source = s.get("source", "").lower()

            if query_lower in name or query_lower in source:
                results.append(self._convert_to_remote_skill(s, installed))

        return results

    async def get_skill_detail(self, name: str) -> Optional[SkillDetail]:
        """Get detailed skill information including SKILL.md content."""
        raw_skills = await self.fetch_index()
        installed = self._get_installed_skills()

        # Find the skill
        target = None
        for s in raw_skills:
            skill_name = s.get("name") or s.get("skillId", "")
            if skill_name == name:
                target = s
                break

        if not target:
            return None

        # Get basic info
        basic = self._convert_to_remote_skill(target, installed)

        # Fetch SKILL.md content from GitHub
        readme = None
        required_tools = []
        examples = []

        source = target.get("source", "")
        skill_id = target.get("skillId") or target.get("name", "")
        if source and skill_id:
            readme = await self._fetch_skill_content(source, skill_id)

        # Parse frontmatter for description
        if readme:
            desc, req_tools = self._parse_skill_frontmatter(readme)
            if desc:
                basic.description = desc
            required_tools = req_tools

        return SkillDetail(
            name=basic.name,
            version=basic.version,
            description=basic.description,
            author=basic.author,
            category=basic.category,
            tags=basic.tags,
            downloads=basic.downloads,
            rating=basic.rating,
            is_installed=basic.is_installed,
            readme=readme,
            required_tools=required_tools,
            examples=examples,
            changelog=None,
        )

    async def _fetch_skill_content(self, source: str, skill_id: str) -> Optional[str]:
        """Fetch SKILL.md content from GitHub."""
        # Try different possible paths
        paths = [
            f"{GITHUB_RAW_BASE}/{source}/main/skills/{skill_id}/SKILL.md",
            f"{GITHUB_RAW_BASE}/{source}/main/skills/{skill_id}/skill.md",
            f"{GITHUB_RAW_BASE}/{source}/master/skills/{skill_id}/SKILL.md",
        ]

        async with httpx.AsyncClient(timeout=15.0) as client:
            for url in paths:
                try:
                    resp = await client.get(url)
                    if resp.status_code == 200:
                        logger.info(f"Fetched skill content from {url}")
                        return resp.text
                except Exception as e:
                    logger.debug(f"Failed to fetch {url}: {e}")

        return None

    def _parse_skill_frontmatter(self, content: str) -> tuple[str, list[str]]:
        """Parse YAML frontmatter from skill content."""
        description = ""
        required_tools = []

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1]
                for line in frontmatter.split("\n"):
                    line = line.strip()
                    if line.startswith("description:"):
                        description = line[12:].strip().strip('"\'')
                    elif line.startswith("tools:"):
                        # Parse tools list
                        tools_str = line[6:].strip()
                        if tools_str.startswith("["):
                            try:
                                required_tools = json.loads(tools_str)
                            except:
                                pass

        return description, required_tools

    def _sanitize_skill_name(self, name: str) -> str:
        """Sanitize skill name for filesystem."""
        safe_name = re.sub(r"[^a-zA-Z0-9_-]", "", name)
        if not safe_name or safe_name.startswith("."):
            raise ValueError(f"Invalid skill name: {name}")
        return safe_name

    async def install_skill(
        self,
        name: str,
        version: Optional[str] = None,
    ) -> dict:
        """Install a skill from skills.sh."""
        safe_name = self._sanitize_skill_name(name)

        # Get skill info
        raw_skills = await self.fetch_index()
        target = None
        for s in raw_skills:
            skill_name = s.get("name") or s.get("skillId", "")
            if skill_name == name:
                target = s
                break

        if not target:
            raise RuntimeError(f"Skill '{name}' not found in registry")

        # Fetch skill content from GitHub
        source = target.get("source", "")
        skill_id = target.get("skillId") or target.get("name", "")
        skill_content = None

        if source and skill_id:
            skill_content = await self._fetch_skill_content(source, skill_id)

        if not skill_content:
            raise RuntimeError(f"Failed to download skill '{name}' content")

        # Create skill directory
        skill_dir = self.skills_dir / safe_name
        skill_dir.mkdir(parents=True, exist_ok=True)

        # Write SKILL.md
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(skill_content, encoding="utf-8")

        # Write metadata
        meta = {
            "source": source,
            "skillId": skill_id,
            "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        meta_file = skill_dir / "metadata.json"
        meta_file.write_text(json.dumps(meta, indent=2), encoding="utf-8")

        logger.info(f"Installed skill '{name}' from {source}")
        return {
            "status": "ok",
            "skill_name": name,
            "version": version or "1.0.0",
            "message": f"Successfully installed skill '{name}' from {source}",
        }

    def uninstall_skill(self, name: str) -> dict:
        """Uninstall a locally installed skill."""
        safe_name = self._sanitize_skill_name(name)
        skill_dir = self.skills_dir / safe_name

        if not skill_dir.exists():
            raise FileNotFoundError(f"Skill '{name}' is not installed")

        # Security check
        try:
            skill_dir.resolve().relative_to(self.skills_dir.resolve())
        except ValueError:
            raise ValueError("Invalid skill path")

        shutil.rmtree(skill_dir)
        logger.info(f"Uninstalled skill '{name}'")
        return {
            "status": "ok",
            "skill_name": name,
            "message": f"Successfully uninstalled skill '{name}'",
        }

    async def update_skill(self, name: str) -> dict:
        """Update an installed skill to the latest version."""
        safe_name = self._sanitize_skill_name(name)
        skill_dir = self.skills_dir / safe_name

        if not skill_dir.exists():
            raise FileNotFoundError(f"Skill '{name}' is not installed")

        # Re-install to update
        return await self.install_skill(name)

    def get_categories(self) -> list[str]:
        """Get available skill categories."""
        return [
            "utility",
            "data",
            "web",
            "automation",
            "integration",
            "other",
        ]
