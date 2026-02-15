"use client";

import React, { useState, useEffect } from "react";
import {
    Dialog,
    DialogContent,
    DialogHeader,
    DialogTitle,
    DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { type McpServerConfig } from "@/lib/api";

interface McpServerDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSave: (name: string, config: McpServerConfig) => void;
    initialName?: string;
    initialConfig?: Partial<McpServerConfig>;
    mode?: "add" | "edit";
}

export default function McpServerDialog({
    open,
    onOpenChange,
    onSave,
    initialName = "",
    initialConfig,
    mode = "add",
}: McpServerDialogProps) {
    const [name, setName] = useState(initialName);
    const [transport, setTransport] = useState<"stdio" | "sse">(
        initialConfig?.transport || "stdio"
    );
    const [command, setCommand] = useState(initialConfig?.command || "");
    const [args, setArgs] = useState(initialConfig?.args?.join(", ") || "");
    const [envStr, setEnvStr] = useState(
        initialConfig?.env ? JSON.stringify(initialConfig.env) : ""
    );
    const [url, setUrl] = useState(initialConfig?.url || "");
    const [headersStr, setHeadersStr] = useState(
        initialConfig?.headers ? JSON.stringify(initialConfig.headers) : ""
    );
    const [description, setDescription] = useState(initialConfig?.description || "");
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        if (open) {
            setName(initialName);
            setTransport(initialConfig?.transport || "stdio");
            setCommand(initialConfig?.command || "");
            setArgs(initialConfig?.args?.join(", ") || "");
            setEnvStr(initialConfig?.env ? JSON.stringify(initialConfig.env) : "");
            setUrl(initialConfig?.url || "");
            setHeadersStr(
                initialConfig?.headers ? JSON.stringify(initialConfig.headers) : ""
            );
            setDescription(initialConfig?.description || "");
        }
    }, [open, initialName, initialConfig]);

    const handleSave = async () => {
        if (!name.trim()) return;

        setSaving(true);
        try {
            const config: McpServerConfig = {
                transport,
                enabled: true,
                description: description.trim(),
            };

            if (transport === "stdio") {
                config.command = command.trim();
                config.args = args
                    .split(",")
                    .map((s) => s.trim())
                    .filter(Boolean);
                if (envStr.trim()) {
                    try {
                        config.env = JSON.parse(envStr);
                    } catch {
                        // ignore invalid JSON
                    }
                }
            } else {
                config.url = url.trim();
                if (headersStr.trim()) {
                    try {
                        config.headers = JSON.parse(headersStr);
                    } catch {
                        // ignore invalid JSON
                    }
                }
            }

            onSave(name.trim(), config);
            onOpenChange(false);
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="sm:max-w-md">
                <DialogHeader>
                    <DialogTitle>
                        {mode === "add" ? "添加 MCP Server" : "编辑 MCP Server"}
                    </DialogTitle>
                </DialogHeader>

                <div className="space-y-4 py-2">
                    {/* Name */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-medium">名称</label>
                        <Input
                            value={name}
                            onChange={(e) => setName(e.target.value)}
                            placeholder="my-server"
                            disabled={mode === "edit"}
                            className="h-8 text-sm"
                        />
                    </div>

                    {/* Transport */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-medium">传输方式</label>
                        <div className="flex gap-2">
                            <Button
                                variant={transport === "stdio" ? "default" : "outline"}
                                size="sm"
                                className="h-7 text-xs flex-1"
                                onClick={() => setTransport("stdio")}
                            >
                                stdio (本地进程)
                            </Button>
                            <Button
                                variant={transport === "sse" ? "default" : "outline"}
                                size="sm"
                                className="h-7 text-xs flex-1"
                                onClick={() => setTransport("sse")}
                            >
                                SSE (远程 HTTP)
                            </Button>
                        </div>
                    </div>

                    {/* stdio fields */}
                    {transport === "stdio" && (
                        <>
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium">命令 (Command)</label>
                                <Input
                                    value={command}
                                    onChange={(e) => setCommand(e.target.value)}
                                    placeholder="npx"
                                    className="h-8 text-sm font-mono"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium">参数 (Args, 逗号分隔)</label>
                                <Input
                                    value={args}
                                    onChange={(e) => setArgs(e.target.value)}
                                    placeholder="-y, @modelcontextprotocol/server-filesystem, /tmp"
                                    className="h-8 text-sm font-mono"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium">
                                    环境变量 (JSON, 可选)
                                </label>
                                <Input
                                    value={envStr}
                                    onChange={(e) => setEnvStr(e.target.value)}
                                    placeholder='{"API_KEY": "..."}'
                                    className="h-8 text-sm font-mono"
                                />
                            </div>
                        </>
                    )}

                    {/* SSE fields */}
                    {transport === "sse" && (
                        <>
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium">URL</label>
                                <Input
                                    value={url}
                                    onChange={(e) => setUrl(e.target.value)}
                                    placeholder="http://localhost:3001/sse"
                                    className="h-8 text-sm font-mono"
                                />
                            </div>
                            <div className="space-y-1.5">
                                <label className="text-xs font-medium">
                                    Headers (JSON, 可选)
                                </label>
                                <Input
                                    value={headersStr}
                                    onChange={(e) => setHeadersStr(e.target.value)}
                                    placeholder='{"Authorization": "Bearer ..."}'
                                    className="h-8 text-sm font-mono"
                                />
                            </div>
                        </>
                    )}

                    {/* Description */}
                    <div className="space-y-1.5">
                        <label className="text-xs font-medium">描述 (可选)</label>
                        <Input
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                            placeholder="本地文件系统访问"
                            className="h-8 text-sm"
                        />
                    </div>
                </div>

                <DialogFooter>
                    <Button
                        variant="outline"
                        size="sm"
                        onClick={() => onOpenChange(false)}
                    >
                        取消
                    </Button>
                    <Button
                        size="sm"
                        onClick={handleSave}
                        disabled={!name.trim() || saving}
                    >
                        {saving ? "保存中..." : "保存"}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
