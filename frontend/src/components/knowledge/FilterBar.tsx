import { Search, ChevronDown } from 'lucide-react'
import clsx from 'clsx'

interface FilterBarProps {
  search: string
  onSearchChange: (value: string) => void
  sourceType: string
  onSourceTypeChange: (value: string) => void
  status: string
  onStatusChange: (value: string) => void
  total: number
}

const selectClass = clsx(
  'bg-[#1f1f1f] border border-[#2a2a2a] text-[#888888] text-sm rounded-lg',
  'px-3 py-2 pr-8 outline-none cursor-pointer transition-colors',
  'hover:border-[#3d3d3d] focus:border-[#7c3aed] focus:ring-1 focus:ring-[#7c3aed]/30',
  'appearance-none'
)

interface SelectWrapProps {
  value: string
  onChange: (v: string) => void
  children: React.ReactNode
  className?: string
}

function SelectWrap({ value, onChange, children, className }: SelectWrapProps) {
  return (
    <div className="relative">
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={clsx(selectClass, className)}
      >
        {children}
      </select>
      <div className="absolute inset-y-0 right-2 flex items-center pointer-events-none">
        <ChevronDown size={14} className="text-[#555555]" />
      </div>
    </div>
  )
}

export default function FilterBar({
  search,
  onSearchChange,
  sourceType,
  onSourceTypeChange,
  status,
  onStatusChange,
  total,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-center gap-3">
      {/* Search input */}
      <div className="relative flex-1 min-w-[200px]">
        <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
          <Search size={15} className="text-[#555555]" />
        </div>
        <input
          type="text"
          value={search}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Search knowledge..."
          className={clsx(
            'w-full pl-9 pr-4 py-2 bg-[#1f1f1f] border border-[#2a2a2a] rounded-lg',
            'text-sm text-[#e8e8e8] placeholder:text-[#555555] outline-none transition-colors',
            'hover:border-[#3d3d3d] focus:border-[#7c3aed] focus:ring-1 focus:ring-[#7c3aed]/30'
          )}
        />
      </div>

      {/* Source type filter */}
      <SelectWrap value={sourceType} onChange={onSourceTypeChange}>
        <option value="all">All Sources</option>
        <option value="youtube">YouTube</option>
        <option value="article">Article</option>
        <option value="pdf">PDF</option>
      </SelectWrap>

      {/* Status filter */}
      <SelectWrap value={status} onChange={onStatusChange}>
        <option value="all">All Status</option>
        <option value="completed">Completed</option>
        <option value="processing">Processing</option>
        <option value="failed">Failed</option>
      </SelectWrap>

      {/* Result count */}
      <span className="text-sm text-[#555555] whitespace-nowrap ml-auto">
        {total.toLocaleString()} {total === 1 ? 'item' : 'items'}
      </span>
    </div>
  )
}
