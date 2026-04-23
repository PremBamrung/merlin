import { useState, useCallback } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Plus, BookOpen, ChevronLeft, ChevronRight } from 'lucide-react'
import clsx from 'clsx'
import { fetchKnowledge, deleteKnowledgeItem } from '@/api/knowledge'
import { useUIStore } from '@/stores/uiStore'
import KnowledgeCard from '@/components/knowledge/KnowledgeCard'
import FilterBar from '@/components/knowledge/FilterBar'
import KnowledgeDetail from '@/components/knowledge/KnowledgeDetail'
import type { KnowledgeItem } from '@/types'

const PER_PAGE = 20

function SkeletonCard() {
  return (
    <div className="bg-[#161616] rounded-xl border border-[#2a2a2a] overflow-hidden animate-pulse">
      <div className="aspect-video bg-[#1f1f1f]" />
      <div className="p-3 space-y-2">
        <div className="h-3 bg-[#2a2a2a] rounded w-4/5" />
        <div className="h-3 bg-[#2a2a2a] rounded w-3/5" />
        <div className="h-2.5 bg-[#2a2a2a] rounded w-2/5 mt-2" />
      </div>
    </div>
  )
}

export default function KnowledgePage() {
  const setAddSourceOpen = useUIStore((s) => s.setAddSourceOpen)

  const [search, setSearch] = useState('')
  const [sourceType, setSourceType] = useState('all')
  const [status, setStatus] = useState('all')
  const [page, setPage] = useState(1)
  const [selectedItem, setSelectedItem] = useState<KnowledgeItem | null>(null)

  // Debounced search — reset page on filter change
  const handleSearchChange = useCallback((value: string) => {
    setSearch(value)
    setPage(1)
  }, [])

  const handleSourceTypeChange = useCallback((value: string) => {
    setSourceType(value)
    setPage(1)
  }, [])

  const handleStatusChange = useCallback((value: string) => {
    setStatus(value)
    setPage(1)
  }, [])

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['knowledge', { page, search, sourceType, status }],
    queryFn: () =>
      fetchKnowledge({
        page,
        per_page: PER_PAGE,
        search: search || undefined,
        source_type: sourceType !== 'all' ? sourceType : undefined,
        status: status !== 'all' ? status : undefined,
      }),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  })

  async function handleDelete(id: string) {
    try {
      await deleteKnowledgeItem(id)
      // Close detail if open
      if (selectedItem?.id === id) setSelectedItem(null)
    } catch (err) {
      console.error('Failed to delete:', err)
    }
  }

  const total = data?.total ?? 0
  const totalPages = Math.ceil(total / PER_PAGE)
  const items = data?.items ?? []

  return (
    <div className="h-full flex flex-col">
      {/* Page header */}
      <div className="flex-shrink-0 px-6 py-5 border-b border-[#2a2a2a] flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-[#e8e8e8]">Knowledge Base</h1>
          <p className="text-xs text-[#555555] mt-0.5">
            Your saved content, organized and searchable
          </p>
        </div>
        <button
          onClick={() => setAddSourceOpen(true)}
          className="flex items-center gap-2 px-4 py-2 bg-[#7c3aed] hover:bg-[#6d28d9] text-white text-sm font-medium rounded-lg transition-colors"
        >
          <Plus size={16} />
          Add Source
        </button>
      </div>

      {/* Filters */}
      <div className="flex-shrink-0 px-6 py-3 border-b border-[#2a2a2a]">
        <FilterBar
          search={search}
          onSearchChange={handleSearchChange}
          sourceType={sourceType}
          onSourceTypeChange={handleSourceTypeChange}
          status={status}
          onStatusChange={handleStatusChange}
          total={total}
        />
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto px-6 py-5">
        {isError && (
          <div className="flex items-center justify-center h-40">
            <div className="text-center">
              <p className="text-[#ef4444] text-sm font-medium">Failed to load knowledge</p>
              <p className="text-[#555555] text-xs mt-1">
                {error instanceof Error ? error.message : 'Unknown error'}
              </p>
            </div>
          </div>
        )}

        {isLoading && !data && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 12 }).map((_, i) => (
              <SkeletonCard key={i} />
            ))}
          </div>
        )}

        {!isLoading && !isError && items.length === 0 && (
          <div className="flex flex-col items-center justify-center h-60 gap-4">
            <div className="w-12 h-12 bg-[#1f1f1f] border border-[#2a2a2a] rounded-xl flex items-center justify-center">
              <BookOpen size={22} className="text-[#555555]" />
            </div>
            <div className="text-center">
              <p className="text-[#888888] text-sm font-medium">
                {search || sourceType !== 'all' || status !== 'all'
                  ? 'No results found'
                  : 'Your knowledge base is empty'}
              </p>
              <p className="text-[#555555] text-xs mt-1">
                {search || sourceType !== 'all' || status !== 'all'
                  ? 'Try adjusting your filters'
                  : 'Add a YouTube video or article to get started'}
              </p>
            </div>
            {!search && sourceType === 'all' && status === 'all' && (
              <button
                onClick={() => setAddSourceOpen(true)}
                className="flex items-center gap-2 px-4 py-2 bg-[#7c3aed] hover:bg-[#6d28d9] text-white text-sm font-medium rounded-lg transition-colors"
              >
                <Plus size={16} />
                Add First Source
              </button>
            )}
          </div>
        )}

        {items.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
            {items.map((item) => (
              <KnowledgeCard
                key={item.id}
                item={item}
                onClick={setSelectedItem}
              />
            ))}
          </div>
        )}

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 mt-8 pb-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className={clsx(
                'p-2 rounded-lg border transition-colors',
                page === 1
                  ? 'border-[#2a2a2a] text-[#555555] cursor-not-allowed'
                  : 'border-[#2a2a2a] text-[#888888] hover:border-[#3d3d3d] hover:text-[#e8e8e8]'
              )}
            >
              <ChevronLeft size={16} />
            </button>

            <div className="flex items-center gap-1">
              {Array.from({ length: Math.min(7, totalPages) }).map((_, i) => {
                let pageNum: number
                if (totalPages <= 7) {
                  pageNum = i + 1
                } else if (page <= 4) {
                  pageNum = i + 1
                } else if (page >= totalPages - 3) {
                  pageNum = totalPages - 6 + i
                } else {
                  pageNum = page - 3 + i
                }

                return (
                  <button
                    key={pageNum}
                    onClick={() => setPage(pageNum)}
                    className={clsx(
                      'w-8 h-8 rounded-lg text-sm transition-colors',
                      pageNum === page
                        ? 'bg-[#7c3aed] text-white font-medium'
                        : 'text-[#888888] hover:bg-[#1f1f1f] hover:text-[#e8e8e8]'
                    )}
                  >
                    {pageNum}
                  </button>
                )
              })}
            </div>

            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className={clsx(
                'p-2 rounded-lg border transition-colors',
                page === totalPages
                  ? 'border-[#2a2a2a] text-[#555555] cursor-not-allowed'
                  : 'border-[#2a2a2a] text-[#888888] hover:border-[#3d3d3d] hover:text-[#e8e8e8]'
              )}
            >
              <ChevronRight size={16} />
            </button>
          </div>
        )}
      </div>

      {/* Detail slide-over */}
      <KnowledgeDetail
        item={selectedItem}
        onClose={() => setSelectedItem(null)}
        onDelete={handleDelete}
      />
    </div>
  )
}
