import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import toast from 'react-hot-toast';
import { useVideos } from '../hooks/useVideos';
import { useVideoStore } from '../stores/videoStore';
import { useJobStore } from '../stores/jobStore';
import { videoService } from '../services/videoService';
import { ConfirmDialog } from '../components/ConfirmDialog';
import { formatDate, formatDuration } from '../lib/utils';
import type { VideoDTO } from '../types';

export default function Database() {
    const { selectedChannelId } = useVideoStore();
    const queryClient = useQueryClient();
    const addJob = useJobStore((state) => state.addJob);

    // Selection state
    const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
    const [selectAll, setSelectAll] = useState(false);

    // Dialog state
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [reprocessDialogOpen, setReprocessDialogOpen] = useState(false);
    const [targetVideoId, setTargetVideoId] = useState<string | null>(null);
    const [actionInProgress, setActionInProgress] = useState(false);

    const channelReady = Boolean(selectedChannelId);
    const { data: videos, isLoading } = useVideos(
        channelReady
            ? {
                channel_id: selectedChannelId || undefined,
                limit: 100
            }
            : undefined,
        { enabled: channelReady }
    );

    // Selection handlers
    const toggleSelectAll = () => {
        if (selectAll) {
            setSelectedIds(new Set());
        } else {
            setSelectedIds(new Set(videos?.map(v => v.id) || []));
        }
        setSelectAll(!selectAll);
    };

    const toggleSelect = (id: string) => {
        const newSet = new Set(selectedIds);
        if (newSet.has(id)) {
            newSet.delete(id);
        } else {
            newSet.add(id);
        }
        setSelectedIds(newSet);
        setSelectAll(newSet.size === videos?.length);
    };

    // Action handlers
    const handleDelete = async (password?: string) => {
        if (!password) return;
        setActionInProgress(true);
        try {
            const targets = targetVideoId ? [targetVideoId] : Array.from(selectedIds);
            for (const id of targets) {
                await videoService.deleteVideo(id, password);
            }
            toast.success(`${targets.length} vídeo(s) excluído(s)`);
            setSelectedIds(new Set());
            setSelectAll(false);
            queryClient.invalidateQueries({ queryKey: ['videos'] });
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : 'Erro ao excluir';
            toast.error(message);
        } finally {
            setActionInProgress(false);
            setDeleteDialogOpen(false);
            setTargetVideoId(null);
        }
    };

    const handleReprocess = async (password?: string) => {
        if (!password) return;
        setActionInProgress(true);
        try {
            const targets = targetVideoId ? [targetVideoId] : Array.from(selectedIds);
            for (const id of targets) {
                const video = videos?.find(v => v.id === id);
                const result = await videoService.reprocessVideo(id, password);
                addJob({
                    jobId: result.job_id,
                    videoId: id,
                    videoTitle: video?.title || 'Vídeo',
                    status: 'queued',
                    progress: 0,
                    startedAt: new Date(),
                });
            }
            toast.success(`${targets.length} vídeo(s) enfileirado(s) para reprocessamento`);
            setSelectedIds(new Set());
            setSelectAll(false);
        } catch (error: unknown) {
            const message = error instanceof Error ? error.message : 'Erro ao reprocessar';
            toast.error(message);
        } finally {
            setActionInProgress(false);
            setReprocessDialogOpen(false);
            setTargetVideoId(null);
        }
    };

    const openDeleteDialog = (videoId?: string) => {
        setTargetVideoId(videoId || null);
        setDeleteDialogOpen(true);
    };

    const openReprocessDialog = (videoId?: string) => {
        setTargetVideoId(videoId || null);
        setReprocessDialogOpen(true);
    };

    return (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {/* Header with title and action buttons */}
            <div className="flex justify-between items-center mb-6">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Banco de Dados de Sermões</h1>
                <div className="flex gap-2">
                    <button
                        disabled={selectedIds.size === 0 || actionInProgress}
                        onClick={() => openReprocessDialog()}
                        className="px-4 py-2 bg-blue-600 text-white rounded-lg disabled:opacity-50 hover:bg-blue-700 transition-colors"
                    >
                        Reprocessar ({selectedIds.size})
                    </button>
                    <button
                        disabled={selectedIds.size === 0 || actionInProgress}
                        onClick={() => openDeleteDialog()}
                        className="px-4 py-2 bg-red-600 text-white rounded-lg disabled:opacity-50 hover:bg-red-700 transition-colors"
                    >
                        Excluir ({selectedIds.size})
                    </button>
                </div>
            </div>

            <div className="bg-white dark:bg-gray-800 shadow overflow-hidden rounded-lg">
                <div className="overflow-x-auto">
                    <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
                        <thead className="bg-gray-50 dark:bg-gray-900">
                            <tr>
                                <th scope="col" className="px-4 py-3 text-left">
                                    <input
                                        type="checkbox"
                                        checked={selectAll}
                                        onChange={toggleSelectAll}
                                        className="w-4 h-4 rounded border-gray-300 dark:border-gray-600"
                                    />
                                </th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Título
                                </th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Data
                                </th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Duração
                                </th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Status
                                </th>
                                <th scope="col" className="px-6 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider">
                                    Ações
                                </th>
                            </tr>
                        </thead>
                        <tbody className="bg-white dark:bg-gray-800 divide-y divide-gray-200 dark:divide-gray-700">
                            {isLoading ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-4 text-center text-gray-500 dark:text-gray-400">Carregando...</td>
                                </tr>
                            ) : videos?.length === 0 ? (
                                <tr>
                                    <td colSpan={6} className="px-6 py-4 text-center text-gray-500 dark:text-gray-400">Nenhum vídeo encontrado</td>
                                </tr>
                            ) : videos?.map((video: VideoDTO) => (
                                <tr key={video.id} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                                    <td className="px-4 py-4">
                                        <input
                                            type="checkbox"
                                            checked={selectedIds.has(video.id)}
                                            onChange={() => toggleSelect(video.id)}
                                            className="w-4 h-4 rounded border-gray-300 dark:border-gray-600"
                                        />
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <div className="text-sm font-medium text-gray-900 dark:text-white">{video.title}</div>
                                        <div className="text-sm text-gray-500 dark:text-gray-400">{video.youtube_id}</div>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                        {formatDate(video.published_at || video.created_at)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 dark:text-gray-400">
                                        {formatDuration(video.duration)}
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap">
                                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full
                                            ${video.status === 'PROCESSED' ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300' :
                                            video.status === 'FAILED' ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300' :
                                            'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-300'}`}>
                                            {video.status}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                                        <div className="flex gap-2">
                                            <button
                                                onClick={() => openReprocessDialog(video.id)}
                                                disabled={actionInProgress}
                                                className="text-blue-600 hover:text-blue-800 dark:text-blue-400 dark:hover:text-blue-300 disabled:opacity-50"
                                            >
                                                Reprocessar
                                            </button>
                                            <button
                                                onClick={() => openDeleteDialog(video.id)}
                                                disabled={actionInProgress}
                                                className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 disabled:opacity-50"
                                            >
                                                Excluir
                                            </button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            {/* Confirmation Dialogs */}
            <ConfirmDialog
                isOpen={deleteDialogOpen}
                title="Confirmar Exclusão"
                message={`Deseja excluir ${targetVideoId ? '1' : selectedIds.size} vídeo(s)? Esta ação é irreversível.`}
                variant="danger"
                requirePassword
                confirmLabel="Excluir"
                onConfirm={handleDelete}
                onCancel={() => { setDeleteDialogOpen(false); setTargetVideoId(null); }}
            />

            <ConfirmDialog
                isOpen={reprocessDialogOpen}
                title="Confirmar Reprocessamento"
                message={`Deseja reprocessar ${targetVideoId ? '1' : selectedIds.size} vídeo(s)? Isso vai substituir toda a análise de IA.`}
                variant="warning"
                requirePassword
                confirmLabel="Reprocessar"
                onConfirm={handleReprocess}
                onCancel={() => { setReprocessDialogOpen(false); setTargetVideoId(null); }}
            />
        </div>
    );
}
