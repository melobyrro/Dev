import { useVideos } from '../hooks/useVideos';
import { useVideoStore } from '../stores/videoStore';
import { MonthlyGroup } from './MonthlyGroup';
import { groupVideosByMonth } from '../lib/utils';
import { config } from '../lib/config';
import { VideoDetailDrawer } from './VideoDetailDrawer';

export function VideoList() {
  const { filters, setFilter, clearFilters } = useVideoStore();

  const { data: videos, isLoading, error, refetch } = useVideos({
    channel_id: config.defaultChannelId,
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

  if (!videos || videos.length === 0) {
    return (
      <div
        data-testid="empty-state"
        className="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-12 text-center"
      >
        <svg
          className="mx-auto h-12 w-12 text-gray-400 mb-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z"
          />
        </svg>
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          Nenhum vídeo encontrado
        </h3>
        <p className="text-gray-600 dark:text-gray-400">
          Não há vídeos que correspondam aos filtros selecionados.
        </p>
      </div>
    );
  }

  return (
    <>
      <div>
        <div className="mb-6 flex gap-4">
          <div className="flex-1">
            <input
              data-testid="video-search"
              type="text"
              placeholder="Buscar por título..."
              value={filters.search || ''}
              onChange={(e) => setFilter('search', e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 dark:bg-gray-800 dark:text-white"
            />
          </div>
          <select
            data-testid="status-filter"
            value={filters.status || ''}
            onChange={(e) => setFilter('status', e.target.value || undefined)}
            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-indigo-500 dark:bg-gray-800 dark:text-white"
          >
            <option data-testid="filter-option-all" value="">
              Todos os status
            </option>
            <option data-testid="filter-option-COMPLETED" value="PROCESSED">
              Processado
            </option>
            <option data-testid="filter-option-processing" value="PROCESSING">
              Processando
            </option>
            <option data-testid="filter-option-pending" value="PENDING">
              Pendente
            </option>
            <option value="QUEUED">Na fila</option>
            <option value="FAILED">Falhou</option>
          </select>
          {(filters.search || filters.status) && (
            <button
              onClick={clearFilters}
              className="px-4 py-2 text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
            >
              Limpar filtros
            </button>
          )}
        </div>

        <div>
          {monthlyGroups.map((group) => (
            <MonthlyGroup key={group.year + '-' + group.month} group={group} />
          ))}
        </div>
      </div>

      {/* Video Detail Drawer */}
      <VideoDetailDrawer />
    </>
  );
}
