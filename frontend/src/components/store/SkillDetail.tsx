"use client";

import React from "react";
import {
  Download,
  Star,
  Check,
  Loader2,
  ArrowLeft,
  User,
  Tag,
  Wrench,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import type { SkillDetail as SkillDetailType } from "@/lib/api";

interface SkillDetailProps {
  skill: SkillDetailType;
  onBack: () => void;
  onInstall: (name: string) => Promise<void>;
  isInstalling?: boolean;
}

const CATEGORY_LABELS: Record<string, string> = {
  utility: "工具",
  data: "数据",
  web: "网络",
  automation: "自动化",
  integration: "集成",
  other: "其他",
};

export default function SkillDetail({
  skill,
  onBack,
  onInstall,
  isInstalling = false,
}: SkillDetailProps) {
  const handleInstall = async () => {
    await onInstall(skill.name);
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-6 py-4 border-b border-border/50">
        <Button
          variant="ghost"
          size="sm"
          className="mb-3 -ml-2 text-muted-foreground hover:text-foreground"
          onClick={onBack}
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          返回列表
        </Button>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-bold text-foreground">{skill.name}</h2>
            <p className="text-sm text-muted-foreground mt-1">
              {skill.description}
            </p>
          </div>
          {skill.is_installed ? (
            <Button
              variant="outline"
              className="text-green-600 border-green-200 hover:bg-green-50"
              disabled
            >
              <Check className="w-4 h-4 mr-2" />
              已安装
            </Button>
          ) : (
            <Button onClick={handleInstall} disabled={isInstalling}>
              {isInstalling ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  安装中...
                </>
              ) : (
                <>
                  <Download className="w-4 h-4 mr-2" />
                  安装技能
                </>
              )}
            </Button>
          )}
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        <div className="px-6 py-4 space-y-6">
          {/* Meta Info */}
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <User className="w-4 h-4 text-muted-foreground" />
              <span className="text-muted-foreground">作者:</span>
              <span className="font-medium">{skill.author}</span>
            </div>
            <div className="flex items-center gap-2">
              <Tag className="w-4 h-4 text-muted-foreground" />
              <span className="text-muted-foreground">分类:</span>
              <Badge variant="secondary" className="text-xs">
                {CATEGORY_LABELS[skill.category] || skill.category}
              </Badge>
            </div>
            <div className="flex items-center gap-2">
              <Star className="w-4 h-4 text-yellow-500 fill-yellow-500" />
              <span className="text-muted-foreground">评分:</span>
              <span className="font-medium">{skill.rating.toFixed(1)}</span>
            </div>
            <div className="flex items-center gap-2">
              <Download className="w-4 h-4 text-muted-foreground" />
              <span className="text-muted-foreground">下载:</span>
              <span className="font-medium">{skill.downloads}</span>
            </div>
          </div>

          <Separator />

          {/* Required Tools */}
          {skill.required_tools.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm mb-2 flex items-center gap-2">
                <Wrench className="w-4 h-4" />
                所需工具
              </h3>
              <div className="flex flex-wrap gap-2">
                {skill.required_tools.map((tool) => (
                  <Badge key={tool} variant="outline" className="text-xs">
                    {tool}
                  </Badge>
                ))}
              </div>
            </div>
          )}

          {/* Examples */}
          {skill.examples.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm mb-2">使用示例</h3>
              <ul className="space-y-1 text-sm text-muted-foreground">
                {skill.examples.map((example, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span className="text-primary">•</span>
                    <span>{example}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Tags */}
          {skill.tags.length > 0 && (
            <div>
              <h3 className="font-semibold text-sm mb-2">标签</h3>
              <div className="flex flex-wrap gap-2">
                {skill.tags.map((tag) => (
                  <span
                    key={tag}
                    className="px-2 py-1 text-xs rounded-full bg-muted text-muted-foreground"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Readme */}
          {skill.readme && (
            <div>
              <Separator className="my-4" />
              <h3 className="font-semibold text-sm mb-3">技能文档</h3>
              <div className="prose prose-sm max-w-none text-foreground/80">
                <pre className="whitespace-pre-wrap text-xs bg-muted p-4 rounded-lg overflow-x-auto">
                  {skill.readme}
                </pre>
              </div>
            </div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
