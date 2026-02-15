#!/bin/bash
#
# VibeWorker Skills CLI
# Manage skills from the command line
#
# Usage:
#   skills.sh list [--remote]     # List local or remote skills
#   skills.sh search <query>      # Search for skills
#   skills.sh install <name>      # Install a skill
#   skills.sh uninstall <name>    # Uninstall a skill
#   skills.sh update [--all]      # Update skills
#   skills.sh create <name>       # Create a new skill template
#

set -e

# Configuration
API_BASE="${VIBEWORKER_API_BASE:-http://localhost:8088}"
SKILLS_DIR="${VIBEWORKER_SKILLS_DIR:-$(dirname "$0")/../backend/skills}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Check if backend is running
check_backend() {
    if ! curl -s "${API_BASE}/api/health" > /dev/null 2>&1; then
        print_error "Backend is not running at ${API_BASE}"
        print_info "Start the backend with: cd backend && python app.py"
        exit 1
    fi
}

# List skills
cmd_list() {
    local remote=false
    for arg in "$@"; do
        case $arg in
            --remote|-r)
                remote=true
                ;;
        esac
    done

    if [ "$remote" = true ]; then
        check_backend
        print_info "Fetching remote skills..."
        response=$(curl -s "${API_BASE}/api/store/skills")
        echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
skills = data.get('skills', [])
if not skills:
    print('No remote skills found.')
else:
    print(f'Found {len(skills)} remote skills:\n')
    for s in skills:
        installed = '✓' if s.get('is_installed') else ' '
        print(f\"  [{installed}] {s['name']} v{s['version']}\")
        print(f\"      {s['description']}\")
        print(f\"      ⭐ {s['rating']:.1f}  ⬇ {s['downloads']}  📁 {s['category']}\")
        print()
"
    else
        check_backend
        print_info "Fetching local skills..."
        response=$(curl -s "${API_BASE}/api/skills")
        echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
skills = data.get('skills', [])
if not skills:
    print('No local skills installed.')
else:
    print(f'Found {len(skills)} local skills:\n')
    for s in skills:
        print(f\"  • {s['name']}\")
        print(f\"    {s['description']}\")
        print(f\"    Location: {s['location']}\")
        print()
"
    fi
}

# Search skills
cmd_search() {
    if [ -z "$1" ]; then
        print_error "Usage: skills.sh search <query>"
        exit 1
    fi

    check_backend
    local query="$1"
    print_info "Searching for '${query}'..."

    response=$(curl -s "${API_BASE}/api/store/search?q=$(echo -n "$query" | jq -sRr @uri)")
    echo "$response" | python3 -c "
import json, sys
data = json.load(sys.stdin)
results = data.get('results', [])
if not results:
    print('No skills found matching your query.')
else:
    print(f'Found {len(results)} skills:\n')
    for s in results:
        installed = '✓' if s.get('is_installed') else ' '
        print(f\"  [{installed}] {s['name']} v{s['version']}\")
        print(f\"      {s['description']}\")
        tags = ', '.join(s.get('tags', []))
        if tags:
            print(f\"      Tags: {tags}\")
        print()
"
}

# Install skill
cmd_install() {
    if [ -z "$1" ]; then
        print_error "Usage: skills.sh install <skill_name>"
        exit 1
    fi

    check_backend
    local name="$1"
    print_info "Installing skill '${name}'..."

    response=$(curl -s -X POST "${API_BASE}/api/store/install" \
        -H "Content-Type: application/json" \
        -d "{\"skill_name\": \"${name}\"}")

    status=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','error'))")

    if [ "$status" = "ok" ]; then
        version=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('version',''))")
        print_success "Successfully installed ${name} v${version}"
    else
        error=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('detail', d.get('message', 'Unknown error')))")
        print_error "Failed to install: ${error}"
        exit 1
    fi
}

# Uninstall skill
cmd_uninstall() {
    if [ -z "$1" ]; then
        print_error "Usage: skills.sh uninstall <skill_name>"
        exit 1
    fi

    check_backend
    local name="$1"

    read -p "Are you sure you want to uninstall '${name}'? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Cancelled."
        exit 0
    fi

    print_info "Uninstalling skill '${name}'..."

    response=$(curl -s -X DELETE "${API_BASE}/api/skills/${name}")
    status=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','error'))" 2>/dev/null || echo "error")

    if [ "$status" = "ok" ]; then
        print_success "Successfully uninstalled ${name}"
    else
        error=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('detail', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
        print_error "Failed to uninstall: ${error}"
        exit 1
    fi
}

# Update skill
cmd_update() {
    local all=false
    local name=""

    for arg in "$@"; do
        case $arg in
            --all|-a)
                all=true
                ;;
            *)
                name="$arg"
                ;;
        esac
    done

    check_backend

    if [ "$all" = true ]; then
        print_info "Updating all installed skills..."
        response=$(curl -s "${API_BASE}/api/skills")
        skills=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(' '.join([s['name'] for s in d.get('skills',[])]))")

        if [ -z "$skills" ]; then
            print_info "No skills to update."
            exit 0
        fi

        for skill in $skills; do
            print_info "Updating ${skill}..."
            response=$(curl -s -X POST "${API_BASE}/api/skills/${skill}/update")
            status=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','error'))" 2>/dev/null || echo "error")
            if [ "$status" = "ok" ]; then
                print_success "Updated ${skill}"
            else
                print_warning "Failed to update ${skill}"
            fi
        done
        print_success "Update complete."
    elif [ -n "$name" ]; then
        print_info "Updating skill '${name}'..."
        response=$(curl -s -X POST "${API_BASE}/api/skills/${name}/update")
        status=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('status','error'))" 2>/dev/null || echo "error")

        if [ "$status" = "ok" ]; then
            version=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('version',''))")
            print_success "Updated ${name} to v${version}"
        else
            error=$(echo "$response" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('detail', 'Unknown error'))" 2>/dev/null || echo "Unknown error")
            print_error "Failed to update: ${error}"
            exit 1
        fi
    else
        print_error "Usage: skills.sh update <skill_name> or skills.sh update --all"
        exit 1
    fi
}

# Create skill template
cmd_create() {
    if [ -z "$1" ]; then
        print_error "Usage: skills.sh create <skill_name>"
        exit 1
    fi

    local name="$1"
    # Sanitize name: lowercase, underscore only
    name=$(echo "$name" | tr '[:upper:]' '[:lower:]' | tr ' -' '_' | tr -cd 'a-z0-9_')

    if [ -z "$name" ]; then
        print_error "Invalid skill name. Use lowercase letters, numbers, and underscores only."
        exit 1
    fi

    local skill_dir="${SKILLS_DIR}/${name}"

    if [ -d "$skill_dir" ]; then
        print_error "Skill '${name}' already exists at ${skill_dir}"
        exit 1
    fi

    print_info "Creating skill template '${name}'..."

    mkdir -p "$skill_dir"
    cat > "${skill_dir}/SKILL.md" << EOF
---
name: ${name}
description: ${name} 技能描述
---

# ${name}

## 描述

详细描述该技能的功能和用途。

## 使用方法

### 步骤 1: 准备

说明准备工作...

### 步骤 2: 执行

说明具体执行步骤...

### 步骤 3: 结果

说明预期结果...

## 示例

- 示例用法 1
- 示例用法 2

## 备注

- 注意事项 1
- 注意事项 2
EOF

    print_success "Created skill template at ${skill_dir}"
    print_info "Edit ${skill_dir}/SKILL.md to customize your skill."
}

# Show help
cmd_help() {
    echo "VibeWorker Skills CLI"
    echo ""
    echo "Usage:"
    echo "  skills.sh <command> [options]"
    echo ""
    echo "Commands:"
    echo "  list [--remote]     List installed skills (or remote with --remote)"
    echo "  search <query>      Search for skills in the store"
    echo "  install <name>      Install a skill from the store"
    echo "  uninstall <name>    Uninstall an installed skill"
    echo "  update <name>       Update a skill (or --all for all skills)"
    echo "  create <name>       Create a new skill template"
    echo "  help                Show this help message"
    echo ""
    echo "Environment Variables:"
    echo "  VIBEWORKER_API_BASE     Backend API URL (default: http://localhost:8088)"
    echo "  VIBEWORKER_SKILLS_DIR   Skills directory path"
    echo ""
    echo "Examples:"
    echo "  skills.sh list --remote     # List all available skills"
    echo "  skills.sh search weather    # Search for weather-related skills"
    echo "  skills.sh install get_weather"
    echo "  skills.sh create my_skill"
}

# Main
case "${1:-help}" in
    list)
        shift
        cmd_list "$@"
        ;;
    search)
        shift
        cmd_search "$@"
        ;;
    install)
        shift
        cmd_install "$@"
        ;;
    uninstall|remove)
        shift
        cmd_uninstall "$@"
        ;;
    update|upgrade)
        shift
        cmd_update "$@"
        ;;
    create|new)
        shift
        cmd_create "$@"
        ;;
    help|--help|-h)
        cmd_help
        ;;
    *)
        print_error "Unknown command: $1"
        cmd_help
        exit 1
        ;;
esac
