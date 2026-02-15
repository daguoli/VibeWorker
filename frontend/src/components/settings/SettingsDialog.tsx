"use client";

import React, { useState, useEffect } from "react";
import { Settings, Eye, EyeOff, Loader2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
    DialogTrigger,
} from "@/components/ui/dialog";
import { fetchSettings, updateSettings, type SettingsData } from "@/lib/api";

function SettingsField({
    label,
    value,
    onChange,
    placeholder,
    type = "text",
    secret = false,
}: {
    label: string;
    value: string;
    onChange: (v: string) => void;
    placeholder?: string;
    type?: string;
    secret?: boolean;
}) {
    const [visible, setVisible] = useState(false);

    return (
        <div className="space-y-1">
            <label className="text-xs font-medium text-muted-foreground">{label}</label>
            <div className="relative">
                <input
                    type={secret && !visible ? "password" : type}
                    value={value}
                    onChange={(e) => onChange(e.target.value)}
                    placeholder={placeholder}
                    className="w-full h-8 px-3 text-xs rounded-lg border border-border bg-background focus:outline-none focus:ring-2 focus:ring-primary/30 transition-all font-mono"
                />
                {secret && (
                    <button
                        type="button"
                        onClick={() => setVisible(!visible)}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted-foreground/50 hover:text-muted-foreground transition-colors"
                    >
                        {visible ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                    </button>
                )}
            </div>
        </div>
    );
}

export default function SettingsDialog() {
    const [open, setOpen] = useState(false);
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [saved, setSaved] = useState(false);
    const [form, setForm] = useState<SettingsData>({
        openai_api_key: "",
        openai_api_base: "",
        llm_model: "",
        llm_temperature: 0.7,
        llm_max_tokens: 4096,
        embedding_api_key: "",
        embedding_api_base: "",
        embedding_model: "",
    });

    useEffect(() => {
        if (open) {
            setLoading(true);
            setSaved(false);
            fetchSettings()
                .then((data) => setForm(data))
                .catch(() => { })
                .finally(() => setLoading(false));
        }
    }, [open]);

    const handleSave = async () => {
        setSaving(true);
        try {
            await updateSettings(form);
            setOpen(false);
        } catch {
            // ignore
        } finally {
            setSaving(false);
        }
    };

    const updateField = (key: keyof SettingsData, value: string | number) => {
        setForm((prev) => ({ ...prev, [key]: value }));
    };

    return (
        <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
                <Button
                    variant="ghost"
                    size="icon"
                    className="w-8 h-8 rounded-lg"
                    id="settings-button"
                >
                    <Settings className="w-4 h-4" />
                </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[480px]">
                <DialogHeader>
                    <DialogTitle className="flex items-center gap-2">
                        <Settings className="w-4 h-4" />
                        模型配置
                    </DialogTitle>
                    <DialogDescription>
                        配置 LLM 和 Embedding 模型的连接参数。保存后需重启后端生效。
                    </DialogDescription>
                </DialogHeader>

                {loading ? (
                    <div className="flex items-center justify-center py-8">
                        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                    </div>
                ) : (
                    <div className="space-y-5 py-2">
                        {/* LLM Section */}
                        <div className="space-y-3">
                            <h4 className="text-xs font-semibold text-foreground/80 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-blue-500" />
                                LLM 模型
                            </h4>
                            <div className="grid gap-3 pl-3.5">
                                <SettingsField
                                    label="API Key"
                                    value={form.openai_api_key}
                                    onChange={(v) => updateField("openai_api_key", v)}
                                    placeholder="sk-..."
                                    secret
                                />
                                <SettingsField
                                    label="API Base URL"
                                    value={form.openai_api_base}
                                    onChange={(v) => updateField("openai_api_base", v)}
                                    placeholder="https://api.openai.com/v1"
                                />
                                <SettingsField
                                    label="模型名称"
                                    value={form.llm_model}
                                    onChange={(v) => updateField("llm_model", v)}
                                    placeholder="gpt-4o"
                                />
                                <div className="grid grid-cols-2 gap-3">
                                    <SettingsField
                                        label="Temperature"
                                        value={String(form.llm_temperature)}
                                        onChange={(v) => updateField("llm_temperature", parseFloat(v) || 0)}
                                        type="number"
                                    />
                                    <SettingsField
                                        label="Max Tokens"
                                        value={String(form.llm_max_tokens)}
                                        onChange={(v) => updateField("llm_max_tokens", parseInt(v) || 4096)}
                                        type="number"
                                    />
                                </div>
                            </div>
                        </div>

                        {/* Embedding Section */}
                        <div className="space-y-3">
                            <h4 className="text-xs font-semibold text-foreground/80 uppercase tracking-wider flex items-center gap-2">
                                <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                Embedding 模型
                            </h4>
                            <div className="grid gap-3 pl-3.5">
                                <SettingsField
                                    label="API Key（留空则复用 LLM）"
                                    value={form.embedding_api_key}
                                    onChange={(v) => updateField("embedding_api_key", v)}
                                    placeholder="留空复用 LLM Key"
                                    secret
                                />
                                <SettingsField
                                    label="API Base URL（留空则复用 LLM）"
                                    value={form.embedding_api_base}
                                    onChange={(v) => updateField("embedding_api_base", v)}
                                    placeholder="留空复用 LLM Base"
                                />
                                <SettingsField
                                    label="模型名称"
                                    value={form.embedding_model}
                                    onChange={(v) => updateField("embedding_model", v)}
                                    placeholder="text-embedding-3-small"
                                />
                            </div>
                        </div>
                    </div>
                )}

                <DialogFooter>
                    {saved && (
                        <span className="text-xs text-emerald-600 mr-auto flex items-center gap-1">
                            ✓ 已保存，重启后端生效
                        </span>
                    )}
                    <Button
                        onClick={handleSave}
                        disabled={saving || loading}
                        size="sm"
                        className="gap-1.5"
                    >
                        {saving ? (
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                            <Save className="w-3.5 h-3.5" />
                        )}
                        保存配置
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
