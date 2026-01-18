import { useState, useEffect } from 'react';
import { useVideos } from '../hooks/useVideos';
import { useVideoStore } from '../stores/videoStore';
import { MonthlyGroup } from './MonthlyGroup';
import { groupVideosByMonth } from '../lib/utils';
import { VideoDetailDrawer } from './VideoDetailDrawer';
import { speakerService } from '../services/speakerService';

export function VideoList() {
  const { filters, setFilter, clearFilters, selectedChannelId } = useVideoStore();

  // Local state mirrors filter form
  const [searchInput, setSearchInput] = useState(filters.search || '');
  const [speakerInput, setSpeakerInput] = useState(filters.speaker || '');
  const [dateStart, setDateStart] = useState(filters.date_start || '');
  const [dateEnd, setDateEnd] = useState(filters.date_end || '');
  const [biblicalRefInput, setBiblicalRefInput] = useState(filters.biblical_ref || '');
  const [showAdvanced, setShowAdvanced] = useState(false);

  const [speakerOptions, setSpeakerOptions] = useState<string[]>([]);

  useEffect(() => {
    setSearchInput(filters.search || '');
    setSpeakerInput(filters.speaker || '');
    setDateStart(filters.date_start || '');
    setDateEnd(filters.date_end || '');
    setBiblicalRefInput(filters.biblical_ref || '');
  }, [filters]);

  const applyFilters = () => {
    setFilter('search', searchInput?.trim() || undefined);
    setFilter('speaker', speakerInput || undefined);
    setFilter('date_start', dateStart || undefined);
    setFilter('date_end', dateEnd || undefined);
    setFilter('biblical_ref', biblicalRefInput?.trim() || undefined);
  };

  const handleClear = () => {
    setSearchInput('');
    setSpeakerInput('');
    setDateStart('');
    setDateEnd('');
    setBiblicalRefInput('');
    clearFilters();
  };

  const fetchSpeakers = async (q?: string) => {
    try {
      const options = await speakerService.autocomplete(selectedChannelId || undefined, q);
      setSpeakerOptions(options.map((o) => o.name));
    } catch (error) {
      console.error('Erro ao carregar pregadores', error);
    }
  };

  useEffect(() => {
    fetchSpeakers();
    // auto-apply when channel changes
    applyFilters();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedChannelId]);

  const { data: videos, isLoading, error, refetch } = useVideos({
    channel_id: selectedChannelId || undefined,
    limit: 50,
    ...filters,
  });

  const monthlyGroups = videos ? groupVideosByMonth(videos) : [];

  if (isLoading) {
    return (
      <div className="space-y-4">
        {[1, 2, 3].map((i) => (
          <div key={i} data-testid="video-skeleton" className="animate-pulse">
            <div className="h-16 bg-gray-200 dark:bg-gray-700 rounded-lg mb-2"></div>
            <div className="h-32 bg-gray-100 dark:bg-gray-800 rounded-lg"></div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        data-testid="error-state"
        className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center"
      >
        <h3 className="text-lg font-semibold text-red-800 dark:text-red-200 mb-2">
          Erro ao carregar vídeos
        </h3>
        <p className="text-red-600 dark:text-red-300 mb-4">
          {error instanceof Error ? error.message : 'Erro desconhecido'}
        </p>
        <button
          data-testid="retry-button"
          onClick={() => refetch()}
          className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
        >
          Tentar novamente
        </button>
      </div>
    );
  }

  const hasVideos = videos && videos.length > 0;

  return (
    <>
      <div className="mb-8 space-y-4">
        <div className="bg-white/80 dark:bg-gray-800/80 backdrop-blur rounded-2xl border border-gray-200 dark:border-gray-700 shadow-sm p-4 md:p-6">
          {/* Main filter row */}
          <div className="flex flex-col md:flex-row md:items-center gap-3">
            <div className="flex-1">
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Busca (título, pregador, texto bíblico, resumo)</label>
              <div className="relative">
                <input
                  data-testid="video-search"
                  type="text"
                  placeholder="Busque em todo o conteúdo do sermão..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') applyFilters();
                  }}
                  className="w-full px-4 py-3 pl-11 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm transition-all"
                />
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
                  <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-4.35-4.35M10.5 18a7.5 7.5 0 100-15 7.5 7.5 0 000 15z" />
                  </svg>
                </span>
              </div>
            </div>
            <div className="w-full md:w-56">
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Pregador</label>
              <select
                value={speakerInput}
                onFocus={() => fetchSpeakers()}
                onChange={(e) => setSpeakerInput(e.target.value)}
                className="w-full px-3 py-3 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm transition-all"
              >
                <option value="">Todos</option>
                {speakerOptions.map((opt) => (
                  <option key={opt} value={opt}>{opt}</option>
                ))}
              </select>
            </div>
            <div className="flex gap-2 w-full md:w-auto">
              <button
                onClick={applyFilters}
                className="flex-1 md:flex-none px-5 py-3 bg-indigo-600 text-white rounded-xl hover:bg-indigo-700 transition-colors shadow-sm"
              >
                Filtrar
              </button>
              <button
                onClick={handleClear}
                className="flex-1 md:flex-none px-5 py-3 bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200 rounded-xl hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors border border-gray-200 dark:border-gray-700"
              >
                Limpar
              </button>
            </div>
          </div>

          {/* Advanced filters toggle */}
          <button
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="mt-3 text-sm text-indigo-600 dark:text-indigo-400 hover:underline flex items-center gap-1"
          >
            <svg className={`w-4 h-4 transition-transform ${showAdvanced ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
            {showAdvanced ? 'Ocultar filtros avançados' : 'Mostrar filtros avançados'}
          </button>

          {/* Advanced filters */}
          {showAdvanced && (
            <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700 flex flex-col md:flex-row md:items-center gap-3">
              <div className="w-full md:w-48">
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Referência Bíblica</label>
                <input
                  type="text"
                  placeholder="Ex: João 3:16"
                  value={biblicalRefInput}
                  onChange={(e) => setBiblicalRefInput(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') applyFilters();
                  }}
                  className="w-full px-3 py-3 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm transition-all"
                />
              </div>
              <div className="w-full md:w-36">
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Data Início</label>
                <input
                  type="date"
                  value={dateStart}
                  onChange={(e) => setDateStart(e.target.value)}
                  className="w-full px-3 py-3 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm transition-all"
                />
              </div>
              <div className="w-full md:w-36">
                <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Data Fim</label>
                <input
                  type="date"
                  value={dateEnd}
                  onChange={(e) => setDateEnd(e.target.value)}
                  className="w-full px-3 py-3 border border-gray-200 dark:border-gray-700 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-transparent bg-white dark:bg-gray-900 text-gray-900 dark:text-white shadow-sm transition-all"
                />
              </div>
            </div>
          )}
        </div>

        {hasVideos ? (
          <div>
            {monthlyGroups.map((group) => (
              <MonthlyGroup key={group.year + '-' + group.month} group={group} />
            ))}
          </div>
        ) : (
          <div
            data-testid="empty-state"
            className="bg-white dark:bg-gray-800 rounded-2xl p-12 text-center shadow-sm max-w-md mx-auto"
          >
            <div className="w-16 h-16 bg-gray-100 dark:bg-gray-700 rounded-full flex items-center justify-center mx-auto mb-6">
              <svg
                className="h-8 w-8 text-gray-400"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
            </div>
            <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
              Nenhum vídeo encontrado
            </h3>
            <p className="text-gray-500 dark:text-gray-400">
              Tente ajustar seus filtros ou buscar por outro termo.
            </p>
          </div>
        )}
      </div>

      {/* Video Detail Drawer */}
      <VideoDetailDrawer />
    </>
  );
}
