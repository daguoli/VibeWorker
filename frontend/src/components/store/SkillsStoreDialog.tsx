"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Search, Store, X, Loader2, RefreshCw, ChevronLeft, ChevronRight } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import SkillCard from "./SkillCard";
import SkillDetail from "./SkillDetail";
import {
  fetchStoreSkills,
  searchStoreSkills,
  fetchSkillDetail,
  installSkill,
  type RemoteSkill,
  type SkillDetail as SkillDetailType,
} from "@/lib/api";

interface SkillsStoreDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSkillInstalled?: () => void;
}

const CATEGORIES = [
  { id: "all", label: "全部" },
  { id: "utility", label: "工具" },
  { id: "data", label: "数据" },
  { id: "web", label: "网络" },
  { id: "automation", label: "自动化" },
  { id: "integration", label: "集成" },
];

const PAGE_SIZE = 12;

export default function SkillsStoreDialog({
  open,
  onOpenChange,
  onSkillInstalled,
}: SkillsStoreDialogProps) {
  const [skills, setSkills] = useState<RemoteSkill[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [selectedSkill, setSelectedSkill] = useState<SkillDetailType | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [category, setCategory] = useState("all");
  const [isLoading, setIsLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);
  const [installingSkill, setInstallingSkill] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  const loadSkills = useCallback(async (pageNum: number = 1) => {
    setIsLoading(true);
    setError(null);
    try {
      const params: { category?: string; page: number; page_size: number } = {
        page: pageNum,
        page_size: PAGE_SIZE,
      };
      if (category !== "all") {
        params.category = category;
      }
      const response = await fetchStoreSkills(params);
      setSkills(response.skills);
      setTotal(response.total);
      setPage(pageNum);
    } catch (e) {
      setError("无法连接到技能商店，请检查网络连接");
      console.error("Failed to load skills:", e);
    } finally {
      setIsLoading(false);
    }
  }, [category]);

  useEffect(() => {
    if (open && !searchQuery) {
      loadSkills(1);
    }
  }, [open, category, loadSkills, searchQuery]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      loadSkills(1);
      return;
    }
    setIsSearching(true);
    setError(null);
    try {
      const results = await searchStoreSkills(searchQuery);
      setSkills(results);
      setTotal(results.length);
      setPage(1);
    } catch (e) {
      setError("搜索失败，请重试");
      console.error("Search failed:", e);
    } finally {
      setIsSearching(false);
    }
  };

  const handleSearchKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const handleSelectSkill = async (skill: RemoteSkill) => {
    try {
      const detail = await fetchSkillDetail(skill.name);
      setSelectedSkill(detail);
    } catch (e) {
      console.error("Failed to fetch skill detail:", e);
      setSelectedSkill({
        ...skill,
        readme: undefined,
        required_tools: [],
        examples: [],
        changelog: undefined,
      });
    }
  };

  const handleInstall = async (name: string) => {
    setInstallingSkill(name);
    try {
      await installSkill(name);
      setSkills((prev) =>
        prev.map((s) => (s.name === name ? { ...s, is_installed: true } : s))
      );
      if (selectedSkill?.name === name) {
        setSelectedSkill((prev) => (prev ? { ...prev, is_installed: true } : null));
      }
      onSkillInstalled?.();
    } catch (e) {
      console.error("Install failed:", e);
      setError(`安装失败: ${e instanceof Error ? e.message : "未知错误"}`);
    } finally {
      setInstallingSkill(null);
    }
  };

  const handleBack = () => {
    setSelectedSkill(null);
  };

  const handlePageChange = (newPage: number) => {
    if (newPage >= 1 && newPage <= totalPages && !searchQuery) {
      loadSkills(newPage);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl h-[80vh] flex flex-col p-0 gap-0 overflow-hidden">
        <DialogHeader className="px-6 py-4 border-b border-border/50 shrink-0">
          <div className="flex items-center justify-between">
            <DialogTitle className="flex items-center gap-2 text-lg">
              <Store className="w-5 h-5 text-primary" />
              技能商店
              {total > 0 && (
                <span className="text-sm font-normal text-muted-foreground">
                  ({total} 个技能)
                </span>
              )}
            </DialogTitle>
          </div>
        </DialogHeader>

        {selectedSkill ? (
          <SkillDetail
            skill={selectedSkill}
            onBack={handleBack}
            onInstall={handleInstall}
            isInstalling={installingSkill === selectedSkill.name}
          />
        ) : (
          <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
            {/* Search Bar */}
            <div className="px-6 py-3 border-b border-border/30 shrink-0">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                  <Input
                    placeholder="搜索技能名称、描述或标签..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    onKeyDown={handleSearchKeyDown}
                    className="pl-9"
                  />
                  {searchQuery && (
                    <button
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      onClick={() => {
                        setSearchQuery("");
                        loadSkills(1);
                      }}
                    >
                      <X className="w-4 h-4" />
                    </button>
                  )}
                </div>
                <Button onClick={handleSearch} disabled={isSearching}>
                  {isSearching ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    "搜索"
                  )}
                </Button>
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => loadSkills(1)}
                  disabled={isLoading}
                  title="刷新"
                >
                  <RefreshCw
                    className={`w-4 h-4 ${isLoading ? "animate-spin" : ""}`}
                  />
                </Button>
              </div>
            </div>

            {/* Category Tabs */}
            <div className="px-6 py-2 border-b border-border/30 shrink-0">
              <Tabs value={category} onValueChange={(val) => { setCategory(val); setPage(1); }}>
                <TabsList className="bg-transparent h-auto p-0 gap-1">
                  {CATEGORIES.map((cat) => (
                    <TabsTrigger
                      key={cat.id}
                      value={cat.id}
                      className="px-3 py-1.5 h-auto text-sm data-[state=active]:bg-primary/10 data-[state=active]:text-primary rounded-full"
                    >
                      {cat.label}
                    </TabsTrigger>
                  ))}
                </TabsList>
              </Tabs>
            </div>

            {/* Skills List with Scroll */}
            <ScrollArea className="flex-1 min-h-0">
              <div className="px-6 py-4">
                {error && (
                  <div className="mb-4 p-3 rounded-lg bg-destructive/10 text-destructive text-sm">
                    {error}
                  </div>
                )}

                {isLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                  </div>
                ) : skills.length === 0 ? (
                  <div className="text-center py-12 text-muted-foreground">
                    <Store className="w-12 h-12 mx-auto mb-3 opacity-30" />
                    <p>没有找到技能</p>
                    <p className="text-sm mt-1">
                      {searchQuery ? "尝试其他搜索词" : "请稍后再试"}
                    </p>
                  </div>
                ) : (
                  <div className="grid gap-3">
                    {skills.map((skill) => (
                      <SkillCard
                        key={skill.name}
                        skill={skill}
                        onInstall={handleInstall}
                        onSelect={handleSelectSkill}
                        isInstalling={installingSkill === skill.name}
                      />
                    ))}
                  </div>
                )}
              </div>
            </ScrollArea>

            {/* Pagination */}
            {totalPages > 1 && !searchQuery && (
              <div className="px-6 py-3 border-t border-border/30 shrink-0 flex items-center justify-between">
                <span className="text-sm text-muted-foreground">
                  第 {page} / {totalPages} 页
                </span>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page <= 1 || isLoading}
                  >
                    <ChevronLeft className="w-4 h-4 mr-1" />
                    上一页
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page >= totalPages || isLoading}
                  >
                    下一页
                    <ChevronRight className="w-4 h-4 ml-1" />
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
