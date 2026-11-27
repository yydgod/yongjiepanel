<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Bot,
  ChevronRight,
  Eye,
  EyeOff,
  FileCode2,
  FilePlus2,
  Folder,
  FolderPlus,
  FolderTree,
  HardDrive,
  Loader2,
  Pencil,
  RefreshCw,
  Save,
  Search,
  Star,
  Trash2,
  X,
} from 'lucide-vue-next'
import { filesApi } from '../api/files'
import { dshApi } from '../api/dsh'
import { errorMessage } from '../api/client'
import { formatBytes, relativeTime } from '../utils/format'
import type { DshWorkspaceCreate, FileContent, FileEntry } from '../types'

const treeKey = ref(0)
const rootPath = ref('/')
const loadingTree = ref(false)
const showHidden = ref(false)

const selectedEntry = ref<FileEntry | null>(null)
const currentDir = ref('/')
const currentFile = ref<FileContent | null>(null)
const draft = ref('')
const loadingFile = ref(false)
const saving = ref(false)

const dirEntries = ref<FileEntry[]>([])
const loadingDir = ref(false)
let dirRequest = 0

const searchQuery = ref('')
const searchResults = ref<FileEntry[]>([])
const searchOpen = ref(false)
const searching = ref(false)
const searchTruncated = ref(false)
let searchTimer: number | null = null
let searchRequest = 0

const workspaceDialog = ref(false)
const workspaceTitle = ref('')
const creatingWorkspace = ref(false)
const createdWorkspace = ref<DshWorkspaceCreate | null>(null)

interface FileFavorite {
  path: string
  name: string
  is_dir: boolean
}

const FAVORITES_KEY = 'yongjie_file_favorites'
const favorites = ref<FileFavorite[]>(loadFavorites())
const favoritePaths = computed(() => new Set(favorites.value.map((item) => item.path)))
const dirFavorited = computed(() => favoritePaths.value.has(currentDir.value))
const fileFavorited = computed(() =>
  currentFile.value ? favoritePaths.value.has(currentFile.value.path) : false,
)

function loadFavorites(): FileFavorite[] {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY)
    const data = raw ? JSON.parse(raw) : []
    if (!Array.isArray(data)) return []
    const seen = new Set<string>()
    return data.filter((item): item is FileFavorite => {
      if (!item || typeof item.path !== 'string' || !item.path.startsWith('/')) return false
      if (seen.has(item.path)) return false
      seen.add(item.path)
      return true
    })
  } catch {
    return []
  }
}

watch(
  favorites,
  (value) => {
    try {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(value))
    } catch {
      // 隐私模式等场景下静默失败
    }
  },
  { deep: true },
)

function toggleFavorite(path: string, name: string, isDir: boolean): void {
  if (!path) return
  const index = favorites.value.findIndex((item) => item.path === path)
  if (index >= 0) {
    favorites.value.splice(index, 1)
    ElMessage.success('已取消收藏')
    return
  }
  favorites.value.unshift({
    path,
    name: name || path.split('/').filter(Boolean).pop() || path,
    is_dir: isDir,
  })
  if (favorites.value.length > 50) favorites.value.pop()
  ElMessage.success('已收藏')
}

function toggleDirFavorite(): void {
  const name = currentDir.value.split('/').filter(Boolean).pop() ?? '/'
  toggleFavorite(currentDir.value, name, true)
}

function toggleFileFavorite(): void {
  const file = currentFile.value
  if (!file) return
  toggleFavorite(file.path, file.name, false)
}

function openFavorite(item: FileFavorite): void {
  if (item.is_dir) enterDir(item.path)
  else void openFile(item.path)
}

function removeFavorite(path: string): void {
  const index = favorites.value.findIndex((item) => item.path === path)
  if (index >= 0) favorites.value.splice(index, 1)
}

const dirty = computed(() => Boolean(currentFile.value) && draft.value !== currentFile.value?.content)
const lineCount = computed(() => draft.value.split('\n').length)
const crumbs = computed(() => {
  const parts = currentDir.value.split('/').filter(Boolean)
  const list: { label: string; path: string }[] = []
  let acc = ''
  for (const part of parts) {
    acc += `/${part}`
    list.push({ label: part, path: acc })
  }
  return list
})

function joinPath(dir: string, name: string): string {
  const base = dir === '/' ? '' : dir.replace(/\/+$/, '')
  return `${base}/${name.replace(/^\/+/, '')}`
}

function parentOf(path: string): string {
  const index = path.lastIndexOf('/')
  return index <= 0 ? '/' : path.slice(0, index)
}

function entryFromPath(path: string, isDir = false): FileEntry {
  const name = path.split('/').filter(Boolean).pop() ?? path
  return {
    name,
    path,
    is_dir: isDir,
    is_symlink: false,
    size: null,
    mode: '',
    modified_at: null,
    hidden: name.startsWith('.'),
  }
}

function isCancelled(error: unknown): boolean {
  return error === 'cancel' || error === 'close'
}

async function loadNode(node: any, resolve: (entries: FileEntry[]) => void): Promise<void> {
  const path = node.level === 0 ? '/' : (node.data as FileEntry).path
  if (node.level === 0) loadingTree.value = true
  try {
    const listing = await filesApi.list(path)
    rootPath.value = listing.absolute_root || listing.root
    if (listing.truncated) ElMessage.warning('目录条目过多，仅显示前 2000 项')
    resolve(
      listing.items
        .filter((item) => showHidden.value || !item.hidden)
        .map((item) => ({ ...item, leaf: !item.is_dir })),
    )
  } catch (err) {
    ElMessage.error(errorMessage(err))
    resolve([])
  } finally {
    loadingTree.value = false
  }
}

function refreshTree(): void {
  treeKey.value += 1
}

async function loadDir(path: string): Promise<void> {
  const requestId = ++dirRequest
  loadingDir.value = true
  try {
    const listing = await filesApi.list(path)
    if (requestId !== dirRequest) return
    rootPath.value = listing.absolute_root || listing.root
    dirEntries.value = listing.items.filter((item) => showHidden.value || !item.hidden)
  } catch (err) {
    if (requestId === dirRequest) ElMessage.error(errorMessage(err))
  } finally {
    if (requestId === dirRequest) loadingDir.value = false
  }
}

function enterDir(path: string): void {
  fileRequest += 1
  loadingFile.value = false
  currentDir.value = path
  currentFile.value = null
  draft.value = ''
  selectedEntry.value = entryFromPath(path, true)
  searchOpen.value = false
  void loadDir(path)
}

function onNodeClick(data: FileEntry): void {
  selectedEntry.value = data
  if (data.is_dir) {
    enterDir(data.path)
    selectedEntry.value = data
    return
  }
  searchOpen.value = false
  void openFile(data.path)
}

let fileRequest = 0

async function openFile(path: string): Promise<void> {
  const requestId = ++fileRequest
  loadingFile.value = true
  currentDir.value = parentOf(path)
  currentFile.value = null
  draft.value = ''
  try {
    const file = await filesApi.read(path)
    if (requestId !== fileRequest) return
    currentFile.value = file
    draft.value = file.content
    selectedEntry.value = entryFromPath(path)
  } catch (err) {
    if (requestId !== fileRequest) return
    ElMessage.error(errorMessage(err))
  } finally {
    if (requestId === fileRequest) loadingFile.value = false
  }
}

async function saveFile(): Promise<void> {
  const file = currentFile.value
  if (!file) return
  if (!file.editable) {
    ElMessage.warning('该文件为只读预览，无法保存')
    return
  }
  saving.value = true
  try {
    const saved = await filesApi.write(file.path, draft.value)
    currentFile.value = {
      ...file,
      content: draft.value,
      size: saved.size,
      modified_at: saved.modified_at,
    }
    ElMessage.success('已保存')
    refreshTree()
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    saving.value = false
  }
}

async function createEntry(kind: 'file' | 'dir'): Promise<void> {
  const base = currentDir.value
  try {
    const { value } = await ElMessageBox.prompt(
      `在 ${base} 下${kind === 'dir' ? '新建目录' : '新建文件'}`,
      kind === 'dir' ? '新建目录' : '新建文件',
      {
        confirmButtonText: '创建',
        cancelButtonText: '取消',
        inputPlaceholder: kind === 'dir' ? '目录名称' : '文件名称，例如 app.conf',
        inputValidator: (input: string) => {
          const name = input.trim()
          if (!name) return '名称不能为空'
          if (name.includes('/')) return '名称不能包含 /'
          return true
        },
      },
    )
    const target = joinPath(base, value.trim())
    if (kind === 'dir') {
      await filesApi.mkdir(target)
      ElMessage.success('目录已创建')
      refreshTree()
    } else {
      const listing = await filesApi.list(base)
      if (listing.items.some((item) => item.name === value.trim())) {
        ElMessage.error('同名文件已存在')
        return
      }
      await filesApi.write(target, '')
      ElMessage.success('文件已创建')
      refreshTree()
      await openFile(target)
    }
  } catch (err) {
    if (isCancelled(err)) return
    ElMessage.error(errorMessage(err))
  }
}

async function renameCurrent(): Promise<void> {
  const entry = selectedEntry.value
  if (!entry) return
  try {
    const { value } = await ElMessageBox.prompt('输入新的名称', '重命名', {
      confirmButtonText: '重命名',
      cancelButtonText: '取消',
      inputValue: entry.name,
      inputValidator: (input: string) => {
        const name = input.trim()
        if (!name) return '名称不能为空'
        if (name.includes('/')) return '名称不能包含 /'
        return true
      },
    })
    const target = joinPath(parentOf(entry.path), value.trim())
    if (target === entry.path) return
    await filesApi.rename(entry.path, target)
    ElMessage.success('已重命名')
    if (currentFile.value && (currentFile.value.path === entry.path || currentFile.value.path.startsWith(`${entry.path}/`))) {
      await openFile(target + currentFile.value.path.slice(entry.path.length))
    }
    selectedEntry.value = { ...entry, name: value.trim(), path: target }
    currentDir.value = parentOf(target)
    refreshTree()
  } catch (err) {
    if (isCancelled(err)) return
    ElMessage.error(errorMessage(err))
  }
}

async function deleteCurrent(): Promise<void> {
  const entry = selectedEntry.value
  if (!entry) return
  try {
    await ElMessageBox.confirm(
      entry.is_dir
        ? `删除目录「${entry.path}」及其全部内容？该操作不可恢复。`
        : `删除文件「${entry.path}」？该操作不可恢复。`,
      '删除确认',
      { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await filesApi.remove(entry.path, entry.is_dir)
    ElMessage.success('已删除')
    if (currentFile.value && (currentFile.value.path === entry.path || currentFile.value.path.startsWith(`${entry.path}/`))) {
      fileRequest += 1
      loadingFile.value = false
      currentFile.value = null
      draft.value = ''
    }
    selectedEntry.value = null
    currentDir.value = entry.is_dir ? parentOf(entry.path) : currentDir.value
    refreshTree()
  } catch (err) {
    ElMessage.error(errorMessage(err))
  }
}

function goUp(): void {
  if (currentDir.value === '/') return
  enterDir(parentOf(currentDir.value))
}

function toggleHidden(): void {
  showHidden.value = !showHidden.value
  refreshTree()
  void loadDir(currentDir.value)
}

function onSearchFocus(): void {
  if (searchQuery.value.trim()) searchOpen.value = true
}

async function runSearch(query: string): Promise<void> {
  const requestId = ++searchRequest
  try {
    const result = await filesApi.search(query, 40)
    if (requestId !== searchRequest) return
    searchResults.value = result.items
    searchTruncated.value = result.truncated
  } catch (err) {
    if (requestId !== searchRequest) return
    ElMessage.error(errorMessage(err))
  } finally {
    if (requestId === searchRequest) searching.value = false
  }
}

watch(searchQuery, (value) => {
  if (searchTimer) window.clearTimeout(searchTimer)
  searchTimer = null
  const query = value.trim()
  if (!query) {
    searchRequest += 1
    searchOpen.value = false
    searching.value = false
    searchTruncated.value = false
    searchResults.value = []
    return
  }
  searchOpen.value = true
  searching.value = true
  searchTimer = window.setTimeout(() => void runSearch(query), 320)
})

function gotoResult(item: FileEntry): void {
  searchQuery.value = ''
  searchOpen.value = false
  searchResults.value = []
  if (item.is_dir) enterDir(item.path)
  else void openFile(item.path)
}

function openWorkspaceDialog(): void {
  workspaceTitle.value = currentDir.value.split('/').filter(Boolean).pop() ?? ''
  createdWorkspace.value = null
  workspaceDialog.value = true
}

async function submitWorkspace(): Promise<void> {
  creatingWorkspace.value = true
  try {
    const result = await dshApi.createWorkspace(
      currentDir.value,
      workspaceTitle.value.trim() || undefined,
    )
    createdWorkspace.value = result
    if (result.created) ElMessage.success('dsh 工作区已创建')
    else ElMessage.info('该目录已注册过 dsh 工作区')
  } catch (err) {
    ElMessage.error(errorMessage(err))
  } finally {
    creatingWorkspace.value = false
  }
}

function resetWorkspaceDialog(): void {
  createdWorkspace.value = null
  workspaceTitle.value = ''
}

function onKeydown(event: KeyboardEvent): void {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
    if (!currentFile.value) return
    event.preventDefault()
    if (dirty.value) void saveFile()
  }
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  void loadDir('/')
})

onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKeydown)
  if (searchTimer) window.clearTimeout(searchTimer)
})
</script>

<template>
  <div class="space-y-4">
    <header class="flex flex-wrap items-end justify-between gap-3">
      <div>
        <div class="flex items-center gap-2">
          <h1 class="text-[26.4px] font-semibold tracking-tight text-mist-100">服务器文件</h1>
          <span class="rounded-full border border-white/[0.08] bg-white/[0.03] px-2 py-0.5 font-mono text-[12px] text-mist-500">
            FILE MANAGER
          </span>
        </div>
        <p class="mt-1 max-w-2xl text-[14.4px] leading-relaxed text-mist-300">
          浏览服务器文件树，查看与编辑文本文件，支持新建、重命名与删除；所有变更都会写入审计日志。
        </p>
      </div>
      <div class="flex items-center gap-3 text-[13.2px] text-mist-500">
        <span class="flex items-center gap-1.5">
          <HardDrive class="h-3.5 w-3.5 text-aurora-teal" />
          根目录 {{ rootPath }}
        </span>
      </div>
    </header>

    <div class="grid items-start gap-3 lg:grid-cols-[330px_minmax(0,1fr)]">
      <section class="glass-panel flex min-h-[420px] flex-col overflow-hidden lg:h-[calc(100vh-260px)]">
        <div class="flex items-center gap-2 px-3 pb-1.5 pt-3">
          <FolderTree class="h-4 w-4 text-aurora-teal" />
          <span class="text-[13.8px] font-medium text-mist-100">文件树</span>
          <Loader2 v-if="loadingTree" class="ml-auto h-3.5 w-3.5 animate-spin text-mist-500" />
        </div>

        <div class="relative px-3 pb-2">
          <el-input
            v-model="searchQuery"
            size="small"
            placeholder="搜索文件或目录"
            clearable
            @focus="onSearchFocus"
            @keydown.esc="searchOpen = false"
          >
            <template #prefix>
              <Search class="h-3.5 w-3.5" />
            </template>
          </el-input>
          <div
            v-if="searchOpen"
            class="absolute inset-x-3 top-full z-30 max-h-[320px] overflow-auto rounded-xl border border-white/10 bg-ink-900/95 p-1.5 shadow-2xl backdrop-blur-xl"
          >
            <p v-if="searching" class="px-2 py-1.5 text-[12px] text-mist-500">搜索中…</p>
            <p v-else-if="!searchResults.length" class="px-2 py-1.5 text-[12px] text-mist-500">没有匹配结果</p>
            <button
              v-for="item in searchResults"
              :key="item.path"
              type="button"
              class="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left transition-colors hover:bg-white/[0.06]"
              :title="item.path"
              @click="gotoResult(item)"
            >
              <component
                :is="item.is_dir ? Folder : FileCode2"
                class="h-3.5 w-3.5 shrink-0"
                :class="item.is_dir ? 'text-aurora-teal' : 'text-mist-500'"
              />
              <span class="min-w-0 flex-1 truncate font-mono text-[12px] text-mist-300">{{ item.path }}</span>
              <span class="shrink-0 font-mono text-[10.8px] text-mist-500">
                {{ item.is_dir ? '目录' : formatBytes(item.size) }}
              </span>
            </button>
            <p v-if="searchTruncated" class="px-2 pb-1 pt-1.5 text-[10.8px] text-state-warn">
              结果较多，已截断，请缩小关键词
            </p>
          </div>
        </div>

        <div class="mx-2 mb-2 rounded-xl border border-white/[0.06] bg-white/[0.02]">
          <div class="flex items-center gap-1.5 px-2.5 pb-1 pt-2">
            <Star class="h-3 w-3 fill-aurora-teal text-aurora-teal" />
            <span class="text-[11.4px] font-medium text-mist-300">收藏夹</span>
            <span class="ml-auto font-mono text-[10.8px] text-mist-500">{{ favorites.length }}</span>
          </div>
          <div v-if="favorites.length" class="max-h-[132px] overflow-auto px-1 pb-1">
            <div
              v-for="item in favorites"
              :key="item.path"
              class="group flex items-center gap-1.5 rounded-lg px-1.5 py-1 transition-colors hover:bg-white/[0.06]"
            >
              <button
                type="button"
                class="flex min-w-0 flex-1 items-center gap-1.5 text-left"
                :title="item.path"
                @click="openFavorite(item)"
              >
                <component
                  :is="item.is_dir ? Folder : FileCode2"
                  class="h-3 w-3 shrink-0"
                  :class="item.is_dir ? 'text-aurora-teal' : 'text-mist-500'"
                />
                <span class="truncate text-[12px] text-mist-200">{{ item.name }}</span>
              </button>
              <button
                type="button"
                class="shrink-0 cursor-pointer text-mist-500 opacity-0 transition-opacity hover:text-state-bad group-hover:opacity-100"
                title="移除收藏"
                @click="removeFavorite(item.path)"
              >
                <X class="h-3 w-3" />
              </button>
            </div>
          </div>
          <p v-else class="px-2.5 pb-2 text-[11.4px] text-mist-500">
            用右侧星标收藏常用目录或文件
          </p>
        </div>

        <div class="flex flex-wrap items-center gap-1.5 px-3 pb-2">
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" title="在当前目录新建文件" @click="createEntry('file')">
            <FilePlus2 class="h-3.5 w-3.5" />
            文件
          </button>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" title="在当前目录新建目录" @click="createEntry('dir')">
            <FolderPlus class="h-3.5 w-3.5" />
            目录
          </button>
          <button
            type="button"
            class="btn-ghost h-7 px-2 text-[12px]"
            :title="showHidden ? '隐藏以 . 开头的文件' : '显示隐藏文件'"
            @click="toggleHidden"
          >
            <EyeOff v-if="showHidden" class="h-3.5 w-3.5" />
            <Eye v-else class="h-3.5 w-3.5" />
          </button>
          <button type="button" class="btn-ghost h-7 px-2 text-[12px]" title="刷新文件树" @click="refreshTree">
            <RefreshCw class="h-3.5 w-3.5" />
          </button>
        </div>

        <div class="min-h-0 flex-1 overflow-auto px-1.5 pb-2">
          <el-tree
            :key="treeKey"
            lazy
            :load="loadNode"
            :props="{ label: 'name', isLeaf: 'leaf' }"
            node-key="path"
            highlight-current
            @node-click="onNodeClick"
          >
            <template #default="{ data }">
              <span class="flex min-w-0 flex-1 items-center gap-1.5 py-0.5">
                <component
                  :is="data.is_dir ? Folder : FileCode2"
                  class="h-3.5 w-3.5 shrink-0"
                  :class="data.is_dir ? 'text-aurora-teal' : 'text-mist-500'"
                />
                <span class="truncate text-[13.2px]" :class="data.hidden ? 'text-mist-500' : 'text-mist-200'">
                  {{ data.name }}
                </span>
                <span v-if="data.is_symlink" class="shrink-0 font-mono text-[10.2px] text-mist-500">↗</span>
              </span>
            </template>
          </el-tree>
        </div>
      </section>

      <section class="glass-panel flex min-h-[420px] flex-col overflow-hidden lg:h-[calc(100vh-260px)]">
        <template v-if="currentFile">
          <div class="flex flex-wrap items-center gap-2 border-b border-white/[0.06] px-3.5 py-2.5">
            <button
              type="button"
              class="btn-ghost h-7 w-7 justify-center p-0"
              title="返回所在目录"
              @click="enterDir(parentOf(currentFile.path))"
            >
              <ChevronRight class="h-3.5 w-3.5 rotate-180" />
            </button>
            <FileCode2 class="h-4 w-4 shrink-0 text-aurora-teal" />
            <span class="min-w-0 truncate font-mono text-[13.2px] text-mist-100">{{ currentFile.path }}</span>
            <span v-if="dirty" class="rounded bg-state-warn/12 px-1.5 py-0.5 text-[10.8px] text-state-warn">未保存</span>
            <span v-if="!currentFile.editable" class="rounded bg-white/[0.06] px-1.5 py-0.5 text-[10.8px] text-mist-400">只读</span>

            <div class="ml-auto flex items-center gap-1.5">
              <span class="hidden text-[11.4px] text-mist-500 sm:inline">{{ formatBytes(currentFile.size) }}</span>
              <span class="hidden text-[11.4px] text-mist-500 md:inline">{{ relativeTime(currentFile.modified_at) }}</span>
              <button
                type="button"
                class="btn-ghost h-7 w-7 justify-center p-0"
                :title="fileFavorited ? '取消收藏该文件' : '收藏该文件'"
                @click="toggleFileFavorite"
              >
                <Star
                  class="h-3.5 w-3.5"
                  :class="fileFavorited ? 'fill-aurora-teal text-aurora-teal' : 'text-mist-500'"
                />
              </button>
              <button
                type="button"
                class="btn-ghost h-7 px-2 text-[12px]"
                :disabled="!currentFile.editable || !dirty || saving"
                title="保存 (Ctrl + S)"
                @click="saveFile"
              >
                <Save class="h-3.5 w-3.5" :class="saving ? 'animate-pulse' : ''" />
                保存
              </button>
              <button type="button" class="btn-ghost h-7 px-2 text-[12px]" title="重命名" @click="renameCurrent">
                <Pencil class="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                class="btn-ghost h-7 px-2 text-[12px] text-state-bad"
                title="删除"
                @click="deleteCurrent"
              >
                <Trash2 class="h-3.5 w-3.5" />
              </button>
            </div>
          </div>

          <div v-if="currentFile.binary" class="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
            <FileCode2 class="h-8 w-8 text-mist-500" />
            <p class="text-[15px] text-mist-100">二进制文件，无法在线编辑</p>
            <p class="text-[12.6px] text-mist-500">{{ currentFile.mime }} · {{ formatBytes(currentFile.size) }}</p>
          </div>
          <textarea
            v-else
            v-model="draft"
            class="min-h-[320px] w-full flex-1 resize-none bg-transparent px-4 py-3 font-mono text-[12.6px] leading-relaxed text-mist-100 outline-none placeholder:text-mist-500"
            spellcheck="false"
            placeholder="文件内容"
            :readonly="!currentFile.editable"
          />

          <div class="flex flex-wrap items-center gap-3 border-t border-white/[0.06] px-3.5 py-1.5 text-[11.4px] text-mist-500">
            <span>{{ lineCount }} 行 · {{ draft.length }} 字符</span>
            <span class="font-mono">{{ currentFile.mime }}</span>
            <span v-if="currentFile.truncated" class="text-state-warn">文件过大，仅预览前 1 MB</span>
            <span class="ml-auto">Ctrl + S 保存</span>
          </div>
        </template>

        <div v-else-if="loadingFile" class="flex flex-1 flex-col items-center justify-center gap-2 p-8 text-center">
          <Loader2 class="h-6 w-6 animate-spin text-aurora-teal" />
          <p class="text-[13.2px] text-mist-500">正在读取文件…</p>
        </div>

        <template v-else>
          <div class="flex flex-wrap items-center gap-1.5 border-b border-white/[0.06] px-3.5 py-2">
            <button
              type="button"
              class="btn-ghost h-7 w-7 justify-center p-0"
              :disabled="currentDir === '/'"
              title="上级目录"
              @click="goUp"
            >
              <ChevronRight class="h-3.5 w-3.5 rotate-180" />
            </button>
            <button type="button" class="btn-ghost h-7 px-2 font-mono text-[12px]" @click="enterDir('/')">/</button>
            <template v-for="crumb in crumbs" :key="crumb.path">
              <ChevronRight class="h-3 w-3 text-mist-500" />
              <button
                type="button"
                class="btn-ghost h-7 px-2 font-mono text-[12px]"
                @click="enterDir(crumb.path)"
              >
                {{ crumb.label }}
              </button>
            </template>
            <div class="ml-auto flex items-center gap-1.5">
              <span class="text-[11.4px] text-mist-500">{{ dirEntries.length }} 项</span>
              <button type="button" class="btn-ghost h-7 w-7 justify-center p-0" title="刷新目录" @click="loadDir(currentDir)">
                <RefreshCw class="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                class="btn-ghost h-7 w-7 justify-center p-0"
                :title="dirFavorited ? '取消收藏该目录' : '收藏该目录'"
                @click="toggleDirFavorite"
              >
                <Star
                  class="h-3.5 w-3.5"
                  :class="dirFavorited ? 'fill-aurora-teal text-aurora-teal' : 'text-mist-500'"
                />
              </button>
              <button
                type="button"
                class="btn-primary h-7 px-2 text-[12px]"
                title="把当前目录注册为 dsh 工作区"
                @click="openWorkspaceDialog"
              >
                <Bot class="h-3.5 w-3.5" />
                dsh 工作区
              </button>
            </div>
          </div>

          <div class="min-h-0 flex-1 overflow-auto py-1">
            <div v-if="loadingDir" class="flex flex-col items-center justify-center gap-2 p-8 text-center">
              <Loader2 class="h-5 w-5 animate-spin text-aurora-teal" />
              <p class="text-[12.6px] text-mist-500">正在读取目录…</p>
            </div>
            <div v-else-if="!dirEntries.length" class="flex flex-col items-center justify-center gap-2 p-8 text-center">
              <Folder class="h-6 w-6 text-mist-500" />
              <p class="text-[13.2px] text-mist-500">空目录</p>
            </div>
            <button
              v-for="item in dirEntries"
              :key="item.path"
              type="button"
              class="flex w-full items-center gap-2 px-3.5 py-2 text-left transition-colors hover:bg-white/[0.05]"
              @click="item.is_dir ? enterDir(item.path) : openFile(item.path)"
            >
              <component
                :is="item.is_dir ? Folder : FileCode2"
                class="h-3.5 w-3.5 shrink-0"
                :class="item.is_dir ? 'text-aurora-teal' : 'text-mist-500'"
              />
              <span class="min-w-0 truncate text-[13.2px]" :class="item.hidden ? 'text-mist-500' : 'text-mist-200'">
                {{ item.name }}
              </span>
              <span v-if="item.is_symlink" class="shrink-0 font-mono text-[10.2px] text-mist-500">↗</span>
              <span class="ml-auto shrink-0 font-mono text-[11.4px] text-mist-500">
                {{ item.is_dir ? '目录' : formatBytes(item.size) }}
              </span>
              <span class="hidden w-[92px] shrink-0 text-right text-[11.4px] text-mist-500 sm:inline">
                {{ relativeTime(item.modified_at) }}
              </span>
            </button>
          </div>

          <div class="flex items-center gap-2 border-t border-white/[0.06] px-3.5 py-1.5 text-[11.4px] text-mist-500">
            <span class="truncate font-mono">{{ currentDir }}</span>
            <span class="ml-auto shrink-0">选择目录后可创建 dsh 工作区</span>
          </div>
        </template>
      </section>
    </div>

    <el-dialog
      v-model="workspaceDialog"
      title="创建 dsh 工作区"
      width="min(520px, 92vw)"
      destroy-on-close
      @closed="resetWorkspaceDialog"
    >
      <div v-if="!createdWorkspace" class="space-y-3">
        <div class="rounded-lg border border-white/[0.08] bg-white/[0.03] px-3 py-2">
          <div class="label-caps">目录</div>
          <p class="mt-1 break-all font-mono text-[12.6px] text-mist-100">{{ currentDir }}</p>
        </div>
        <div>
          <div class="label-caps mb-1">工作区标题</div>
          <el-input v-model="workspaceTitle" maxlength="120" placeholder="默认使用目录名" />
        </div>
        <p class="text-[12px] leading-relaxed text-mist-500">
          会通过运行中的 dsh 注册该目录，创建后立即可用；若 dsh 未运行，则写入注册表，待 dsh 启动后生效。
        </p>
      </div>

      <div v-else class="space-y-3">
        <div class="rounded-xl border border-state-ok/25 bg-state-ok/8 px-3 py-2 text-[12.6px] text-state-ok">
          {{ createdWorkspace.created ? '工作区已创建' : '该目录已有 dsh 工作区' }}
        </div>
        <div class="text-[12px] text-mist-500">
          工作区 ID：<span class="font-mono text-mist-200">{{ createdWorkspace.workspace_id }}</span>
        </div>
        <p v-if="createdWorkspace.configured && createdWorkspace.url" class="text-[12px] text-mist-500">
          可直接打开工作区，或稍后在 dsh 工作区页签中进入。
        </p>
        <p v-else class="text-[12px] text-state-warn">
          {{ createdWorkspace.reason || 'dsh 尚未配置，工作区已注册，配置后即可打开' }}
        </p>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <template v-if="!createdWorkspace">
            <button type="button" class="btn-ghost" @click="workspaceDialog = false">取消</button>
            <button type="button" class="btn-primary" :disabled="creatingWorkspace" @click="submitWorkspace">
              <Bot class="h-3.5 w-3.5" />
              {{ creatingWorkspace ? '创建中…' : '创建' }}
            </button>
          </template>
          <template v-else>
            <a
              v-if="createdWorkspace.url"
              :href="createdWorkspace.url"
              target="_blank"
              rel="noreferrer"
              class="btn-primary"
            >
              打开工作区
            </a>
            <button type="button" class="btn-ghost" @click="workspaceDialog = false">关闭</button>
          </template>
        </div>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
:deep(.el-tree) {
  background: transparent;
  color: var(--text-2);
}

:deep(.el-tree-node__content) {
  height: 30px;
  border-radius: 8px;
}

:deep(.el-tree-node__content:hover) {
  background: rgb(var(--tint) / 0.06);
}

:deep(.el-tree-node.is-current > .el-tree-node__content) {
  background: rgb(var(--tint) / 0.1);
  color: var(--text-0);
}

:deep(.el-tree__empty-text) {
  color: var(--text-2);
}
</style>
