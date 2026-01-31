import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { useVideoStore } from '../stores/videoStore';

interface Member {
    id: number;
    email: string;
    role: string;
    last_login: string | null;
    login_count: number;
}

interface JobProgress {
    id: string;
    status: string;
    current_step: number;
    steps: Array<{
        name: string;
        status: 'pending' | 'running' | 'completed' | 'failed';
        progress?: number;
    }>;
}

type TabType = 'import' | 'schedule' | 'config' | 'members';

export default function Admin() {
    const { selectedChannelId, channels, fetchChannels } = useVideoStore();
    const [members, setMembers] = useState<Member[]>([]);
    const [channelData, setChannelData] = useState<any>(null);
    const [activeTab, setActiveTab] = useState<TabType>('import');

    const normalizeTime = (time: string | null | undefined) => {
        const match = (time || '').match(/^(\d{1,2}):(\d{2})/);
        if (!match) return '10:00';
        const hours = match[1].padStart(2, '0');
        const minutes = match[2];
        return `${hours}:${minutes}`;
    };

    // Form states
    const [youtubeUrl, setYoutubeUrl] = useState('');
    const [scheduleTime, setScheduleTime] = useState('');
    const [scheduleDay, setScheduleDay] = useState(0);
    const [scheduleEnabled, setScheduleEnabled] = useState(true);
    const [defaultSpeaker, setDefaultSpeaker] = useState('');

    // Import states
    const [importUrl, setImportUrl] = useState('');
    const [bulkStartDate, setBulkStartDate] = useState('');
    const [bulkEndDate, setBulkEndDate] = useState('');
    const [bulkMaxVideos, setBulkMaxVideos] = useState(10);
    const [importProgress, setImportProgress] = useState<JobProgress | null>(null);
    const [importing, setImporting] = useState(false);
    const pollIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    // Config states
    const [geminiApiKey, setGeminiApiKey] = useState('');
    const [currentApiKeyMasked, setCurrentApiKeyMasked] = useState('');
    const [minVideoDuration, setMinVideoDuration] = useState(0);
    const [maxVideoDuration, setMaxVideoDuration] = useState(180);

    // Members modal states
    const [inviteModalOpen, setInviteModalOpen] = useState(false);
    const [inviteEmail, setInviteEmail] = useState('');
    const [inviteRole, setInviteRole] = useState('user');

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        fetchChannels();
    }, []);

    useEffect(() => {
        if (selectedChannelId && channels.length > 0) {
            loadAdminData();
        }
    }, [selectedChannelId, channels]);

    useEffect(() => {
        return () => {
            if (pollIntervalRef.current) {
                clearInterval(pollIntervalRef.current);
            }
        };
    }, []);

    const loadAdminData = async () => {
        setLoading(true);
        try {
            const channel = channels.find(c => c.id.toString() === selectedChannelId);
            if (channel) {
                setChannelData(channel);
                setYoutubeUrl(channel.youtube_url || '');
                setDefaultSpeaker(channel.default_speaker || '');
            }

            // Fetch members
            try {
                const membersRes = await axios.get('/api/church/members', {
                    params: selectedChannelId ? { channel_id: selectedChannelId } : undefined,
                });
                setMembers(membersRes.data.members || []);
            } catch (membersError) {
                console.warn('Members endpoint not available:', membersError);
                setMembers([]);
            }

            // Fetch schedule config
            try {
                const scheduleRes = await axios.get('/api/schedule-config', {
                    params: { channel_id: selectedChannelId }
                });
                const config = scheduleRes.data;
                setScheduleTime(normalizeTime(config.time_of_day));
                setScheduleDay(config.day_of_week ?? 0);
                setScheduleEnabled(config.enabled ?? false);
            } catch (scheduleError) {
                console.warn('Schedule config not available:', scheduleError);
            }

            // Fetch API config
            try {
                const apiConfigRes = await axios.get('/api/admin/settings/api-config', {
                    params: { channel_id: selectedChannelId }
                });
                const lastFive = apiConfigRes.data.gemini_api_key;
                setCurrentApiKeyMasked(lastFive ? `****${lastFive}` : '');
            } catch (apiError) {
                console.warn('API config not available:', apiError);
            }

            // Fetch video duration config
            try {
                const durationRes = await axios.get('/api/admin/settings/video-duration', {
                    params: { channel_id: selectedChannelId }
                });
                setMinVideoDuration(durationRes.data.min_duration_minutes || 0);
                setMaxVideoDuration(durationRes.data.max_duration_minutes || 180);
            } catch (durationError) {
                console.warn('Duration config not available:', durationError);
            }
        } catch (error) {
            console.error('Error loading admin data:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSaveChannel = async () => {
        if (!selectedChannelId) return;
        setSaving(true);
        try {
            await axios.patch(`/api/v2/channels/${selectedChannelId}`, {
                youtube_url: youtubeUrl || null,
                default_speaker: defaultSpeaker || null,
            });
            alert('Canal atualizado com sucesso!');
            await fetchChannels();
            await loadAdminData();
        } catch (error) {
            console.error('Error saving channel:', error);
            alert('Erro ao salvar canal');
        } finally {
            setSaving(false);
        }
    };

    const handleSaveSchedule = async () => {
        setSaving(true);
        const time = normalizeTime(scheduleTime);
        setScheduleTime(time);
        try {
            await axios.put('/api/schedule-config', {
                day_of_week: scheduleDay,
                time_of_day: time,
                enabled: scheduleEnabled
            }, {
                params: { channel_id: selectedChannelId }
            });
            alert('Agendamento atualizado com sucesso!');
            await loadAdminData();
        } catch (error) {
            console.error('Error saving schedule:', error);
            alert('Erro ao salvar agendamento');
        } finally {
            setSaving(false);
        }
    };

    const handleSaveConfig = async () => {
        setSaving(true);
        try {
            if (geminiApiKey) {
                await axios.put('/api/admin/settings/api-config', {
                    gemini_api_key: geminiApiKey
                }, {
                    params: { channel_id: selectedChannelId }
                });
            }
            await axios.put('/api/admin/settings/video-duration', {
                min_duration_minutes: minVideoDuration,
                max_duration_minutes: maxVideoDuration
            }, {
                params: { channel_id: selectedChannelId }
            });
            alert('Configuração salva com sucesso!');
            setGeminiApiKey('');
            await loadAdminData();
        } catch (error) {
            console.error('Error saving config:', error);
            alert('Erro ao salvar configuração');
        } finally {
            setSaving(false);
        }
    };

    const pollJobStatus = async (jobId: string) => {
        try {
            const res = await axios.get(`/api/jobs/${jobId}/status`);
            const job = res.data;

            const progress: JobProgress = {
                id: jobId,
                status: job.status,
                current_step: job.progress || 0,
                steps: [
                    { name: 'Extraindo metadados', status: job.progress >= 10 ? 'completed' : job.progress > 0 ? 'running' : 'pending' },
                    { name: 'Validando duração', status: job.progress >= 20 ? 'completed' : job.progress >= 10 ? 'running' : 'pending' },
                    { name: 'Transcrevendo áudio', status: job.progress >= 50 ? 'completed' : job.progress >= 20 ? 'running' : 'pending', progress: job.progress >= 20 && job.progress < 50 ? ((job.progress - 20) / 30) * 100 : undefined },
                    { name: 'Detectando início', status: job.progress >= 60 ? 'completed' : job.progress >= 50 ? 'running' : 'pending' },
                    { name: 'Análise com IA', status: job.progress >= 70 ? 'completed' : job.progress >= 60 ? 'running' : 'pending' },
                    { name: 'Gerando embeddings', status: job.progress >= 90 ? 'completed' : job.progress >= 70 ? 'running' : 'pending' },
                ]
            };
            setImportProgress(progress);

            if (job.status === 'completed' || job.status === 'failed') {
                if (pollIntervalRef.current) {
                    clearInterval(pollIntervalRef.current);
                    pollIntervalRef.current = null;
                }
                setImporting(false);
                if (job.status === 'completed') {
                    alert('Vídeo importado com sucesso!');
                    setImportUrl('');
                } else {
                    alert(`Erro ao importar: ${job.error_message || 'Erro desconhecido'}`);
                }
            }
        } catch (error) {
            console.error('Error polling job status:', error);
        }
    };

    const handleSingleImport = async () => {
        if (!importUrl.trim()) return;
        setImporting(true);
        setImportProgress(null);
        try {
            const res = await axios.post('/api/videos/import', {
                url: importUrl,
                channel_id: selectedChannelId
            });
            const jobId = res.data.job_id;
            pollIntervalRef.current = setInterval(() => pollJobStatus(jobId), 2000);
        } catch (error: any) {
            console.error('Error importing video:', error);
            alert(error.response?.data?.detail || 'Erro ao importar vídeo');
            setImporting(false);
        }
    };

    const handleBulkImport = async () => {
        setImporting(true);
        try {
            const res = await axios.post('/api/videos/import-bulk', {
                channel_id: selectedChannelId,
                start_date: bulkStartDate || undefined,
                end_date: bulkEndDate || undefined,
                max_videos: bulkMaxVideos
            });
            alert(`Importação em massa iniciada: ${res.data.videos_queued || 0} vídeos na fila`);
        } catch (error: any) {
            console.error('Error bulk importing:', error);
            alert(error.response?.data?.detail || 'Erro ao importar em massa');
        } finally {
            setImporting(false);
        }
    };

    const handleInvite = async () => {
        if (!inviteEmail.trim()) return;
        try {
            const res = await axios.post('/api/church/members/invite', {
                email: inviteEmail,
                role: inviteRole,
                channel_id: selectedChannelId
            });
            if (res.data.success) {
                alert('Membro adicionado!');
                setInviteModalOpen(false);
                setInviteEmail('');
                setInviteRole('user');
                await loadAdminData();
            } else {
                alert(res.data.message);
            }
        } catch (error: any) {
            alert(error.response?.data?.message || 'Erro ao convidar membro');
        }
    };

    const handleRemoveMember = async (memberId: number) => {
        if (!confirm('Remover este membro?')) return;
        try {
            await axios.delete(`/api/church/members/${memberId}`);
            await loadAdminData();
        } catch (error) {
            console.error('Error removing member:', error);
            alert('Erro ao remover membro');
        }
    };

    const formatLastLogin = (dateStr: string | null) => {
        if (!dateStr) return 'Nunca';
        const date = new Date(dateStr);
        return date.toLocaleString('pt-BR');
    };

    const dayNames = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];
    const tabs: { key: TabType; label: string; icon: string }[] = [
        { key: 'import', label: 'Importar', icon: '📥' },
        { key: 'schedule', label: 'Agendamento', icon: '⏰' },
        { key: 'config', label: 'Configuração', icon: '⚙️' },
        { key: 'members', label: 'Membros', icon: '👥' },
    ];

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto p-6 space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                    Administração - {channelData?.title || 'Carregando...'}
                </h1>
            </div>

            {/* Tab Navigation */}
            <div className="border-b border-gray-200 dark:border-gray-700">
                <nav className="flex space-x-4">
                    {tabs.map((tab) => (
                        <button
                            key={tab.key}
                            onClick={() => setActiveTab(tab.key)}
                            className={`px-4 py-3 text-sm font-medium border-b-2 transition-colors ${
                                activeTab === tab.key
                                    ? 'border-blue-600 text-blue-600 dark:text-blue-400'
                                    : 'border-transparent text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
                            }`}
                        >
                            <span className="mr-2">{tab.icon}</span>
                            {tab.label}
                        </button>
                    ))}
                </nav>
            </div>

            {/* Import Tab */}
            {activeTab === 'import' && (
                <div className="space-y-6">
                    {/* Single Import */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                            📥 Importar Vídeo Individual
                        </h2>
                        <div className="flex gap-4">
                            <input
                                type="url"
                                value={importUrl}
                                onChange={(e) => setImportUrl(e.target.value)}
                                placeholder="https://www.youtube.com/watch?v=..."
                                className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                disabled={importing}
                            />
                            <button
                                onClick={handleSingleImport}
                                disabled={importing || !importUrl.trim()}
                                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {importing ? 'Importando...' : 'Importar'}
                            </button>
                        </div>
                    </div>

                    {/* Progress Tracker */}
                    {importProgress && (
                        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
                                Progresso da Importação
                            </h3>
                            <div className="space-y-3">
                                {importProgress.steps.map((step, idx) => (
                                    <div key={idx} className="flex items-center gap-4">
                                        <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                                            step.status === 'completed' ? 'bg-green-500 text-white' :
                                            step.status === 'running' ? 'bg-blue-500 text-white animate-pulse' :
                                            step.status === 'failed' ? 'bg-red-500 text-white' :
                                            'bg-gray-200 dark:bg-gray-700 text-gray-500 dark:text-gray-400'
                                        }`}>
                                            {step.status === 'completed' ? '✓' :
                                             step.status === 'running' ? '⟳' :
                                             step.status === 'failed' ? '✗' : idx + 1}
                                        </div>
                                        <div className="flex-1">
                                            <div className="text-sm font-medium text-gray-900 dark:text-white">
                                                {step.name}
                                            </div>
                                            {step.progress !== undefined && (
                                                <div className="mt-1 w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2">
                                                    <div
                                                        className="bg-blue-600 h-2 rounded-full transition-all"
                                                        style={{ width: `${step.progress}%` }}
                                                    />
                                                </div>
                                            )}
                                        </div>
                                    </div>
                                ))}
                            </div>
                        </div>
                    )}

                    {/* Bulk Import */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                            📦 Importação em Massa
                        </h2>
                        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                            <div>
                                <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
                                    Data Início (opcional)
                                </label>
                                <input
                                    type="date"
                                    value={bulkStartDate}
                                    onChange={(e) => setBulkStartDate(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
                                    Data Fim (opcional)
                                </label>
                                <input
                                    type="date"
                                    value={bulkEndDate}
                                    onChange={(e) => setBulkEndDate(e.target.value)}
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
                                    Máximo de Vídeos
                                </label>
                                <input
                                    type="number"
                                    value={bulkMaxVideos}
                                    onChange={(e) => setBulkMaxVideos(parseInt(e.target.value) || 10)}
                                    min={1}
                                    max={50}
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                />
                            </div>
                        </div>
                        <button
                            onClick={handleBulkImport}
                            disabled={importing}
                            className="px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {importing ? 'Importando...' : 'Iniciar Importação em Massa'}
                        </button>
                    </div>
                </div>
            )}

            {/* Schedule Tab */}
            {activeTab === 'schedule' && (
                <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                    <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                        ⏰ Agendamento Automático
                    </h2>
                    <div className="space-y-4">
                        {/* Enable/Disable Toggle */}
                        <div className="flex items-center gap-4">
                            <label className="flex items-center cursor-pointer">
                                <div className="relative">
                                    <input
                                        type="checkbox"
                                        checked={scheduleEnabled}
                                        onChange={(e) => setScheduleEnabled(e.target.checked)}
                                        className="sr-only"
                                    />
                                    <div className={`block w-14 h-8 rounded-full transition-colors ${scheduleEnabled ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'}`}></div>
                                    <div className={`dot absolute left-1 top-1 bg-white w-6 h-6 rounded-full transition-transform ${scheduleEnabled ? 'transform translate-x-6' : ''}`}></div>
                                </div>
                                <span className="ml-3 text-sm font-medium text-gray-700 dark:text-white">
                                    {scheduleEnabled ? 'Ativado' : 'Desativado'}
                                </span>
                            </label>
                        </div>

                        <div>
                            <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">Horário de Execução</label>
                            <input
                                type="time"
                                value={scheduleTime}
                                onChange={(e) => setScheduleTime(e.target.value)}
                                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">Dia da Semana</label>
                            <div className="grid grid-cols-7 gap-2">
                                {dayNames.map((day, idx) => (
                                    <button
                                        key={idx}
                                        onClick={() => setScheduleDay(idx)}
                                        className={`px-3 py-2 text-sm rounded-lg border transition-colors ${scheduleDay === idx
                                            ? 'bg-blue-600 text-white border-blue-600'
                                            : 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 hover:border-blue-400'
                                        }`}
                                    >
                                        {day}
                                    </button>
                                ))}
                            </div>
                        </div>

                        <p className="text-sm text-gray-600 dark:text-gray-400">
                            {scheduleEnabled ? (
                                <>Próxima execução: {dayNames[scheduleDay]} às {scheduleTime}</>
                            ) : (
                                'Agendamento desativado'
                            )}
                        </p>

                        <button
                            onClick={handleSaveSchedule}
                            disabled={saving}
                            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                            {saving ? 'Salvando...' : 'Atualizar Agendamento'}
                        </button>
                    </div>
                </div>
            )}

            {/* Config Tab */}
            {activeTab === 'config' && (
                <div className="space-y-6">
                    {/* Channel Configuration */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                            📺 Configuração do Canal
                        </h2>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">Link do Canal do YouTube</label>
                                <input
                                    type="url"
                                    value={youtubeUrl}
                                    onChange={(e) => setYoutubeUrl(e.target.value)}
                                    placeholder="https://www.youtube.com/@seucanal"
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                />
                            </div>
                            <div>
                                <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">Pregador Padrão</label>
                                <input
                                    type="text"
                                    value={defaultSpeaker}
                                    onChange={(e) => setDefaultSpeaker(e.target.value)}
                                    placeholder="Nome do pregador padrão"
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                />
                            </div>
                            <button
                                onClick={handleSaveChannel}
                                disabled={saving}
                                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {saving ? 'Salvando...' : 'Salvar Canal'}
                            </button>
                        </div>
                    </div>

                    {/* AI Configuration */}
                    <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                            🤖 Configuração de IA
                        </h2>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">Chave API Gemini</label>
                                <input
                                    type="password"
                                    value={geminiApiKey}
                                    onChange={(e) => setGeminiApiKey(e.target.value)}
                                    placeholder={currentApiKeyMasked || 'Digite a chave API'}
                                    className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                />
                                {currentApiKeyMasked && (
                                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                                        Atual: {currentApiKeyMasked}
                                    </p>
                                )}
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">Duração Mínima (minutos)</label>
                                    <input
                                        type="number"
                                        value={minVideoDuration}
                                        onChange={(e) => setMinVideoDuration(parseInt(e.target.value) || 0)}
                                        min={0}
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">Duração Máxima (minutos)</label>
                                    <input
                                        type="number"
                                        value={maxVideoDuration}
                                        onChange={(e) => setMaxVideoDuration(parseInt(e.target.value) || 180)}
                                        min={1}
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    />
                                </div>
                            </div>
                            <button
                                onClick={handleSaveConfig}
                                disabled={saving}
                                className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                            >
                                {saving ? 'Salvando...' : 'Salvar Configuração'}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            {/* Members Tab */}
            {activeTab === 'members' && (
                <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                    <div className="flex items-center justify-between mb-4">
                        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
                            👥 Membros e Acesso
                        </h2>
                        <button
                            onClick={() => setInviteModalOpen(true)}
                            className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
                        >
                            + Convidar Membro
                        </button>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full">
                            <thead>
                                <tr className="border-b border-gray-200 dark:border-gray-700">
                                    <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-gray-300">Email</th>
                                    <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-gray-300">Perfil</th>
                                    <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-gray-300">Último Login</th>
                                    <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-gray-300">Total Logins</th>
                                    <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-gray-300">Ações</th>
                                </tr>
                            </thead>
                            <tbody>
                                {members.length === 0 ? (
                                    <tr>
                                        <td colSpan={5} className="py-8 text-center text-gray-500 dark:text-gray-400">
                                            Nenhum membro encontrado
                                        </td>
                                    </tr>
                                ) : (
                                    members.map((member) => (
                                        <tr key={member.id} className="border-b border-gray-100 dark:border-gray-700">
                                            <td className="py-3 px-4 text-gray-900 dark:text-white">{member.email}</td>
                                            <td className="py-3 px-4">
                                                <span className={`px-2 py-1 text-xs rounded-full ${
                                                    member.role === 'owner'
                                                        ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300'
                                                        : member.role === 'admin'
                                                            ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
                                                            : 'bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-300'
                                                }`}>
                                                    {member.role === 'owner' ? 'Owner' : member.role === 'admin' ? 'Admin' : 'Usuário'}
                                                </span>
                                            </td>
                                            <td className="py-3 px-4 text-sm text-gray-600 dark:text-gray-400">
                                                {formatLastLogin(member.last_login)}
                                            </td>
                                            <td className="py-3 px-4 text-sm text-gray-600 dark:text-gray-400">
                                                {member.login_count}
                                            </td>
                                            <td className="py-3 px-4">
                                                {member.role !== 'owner' && (
                                                    <button
                                                        onClick={() => handleRemoveMember(member.id)}
                                                        className="text-red-600 hover:text-red-800 dark:text-red-400 dark:hover:text-red-300 text-sm"
                                                    >
                                                        Remover
                                                    </button>
                                                )}
                                            </td>
                                        </tr>
                                    ))
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
            )}

            {/* Invite Modal */}
            {inviteModalOpen && (
                <>
                    <div
                        className="fixed inset-0 bg-black bg-opacity-50 z-40"
                        onClick={() => setInviteModalOpen(false)}
                    />
                    <div className="fixed inset-0 flex items-center justify-center z-50 p-4">
                        <div className="bg-white dark:bg-gray-800 rounded-lg p-6 w-full max-w-md shadow-xl">
                            <h3 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">
                                Convidar Novo Membro
                            </h3>
                            <div className="space-y-4">
                                <div>
                                    <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
                                        Email
                                    </label>
                                    <input
                                        type="email"
                                        value={inviteEmail}
                                        onChange={(e) => setInviteEmail(e.target.value)}
                                        placeholder="usuario@email.com"
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    />
                                </div>
                                <div>
                                    <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-300">
                                        Perfil
                                    </label>
                                    <select
                                        value={inviteRole}
                                        onChange={(e) => setInviteRole(e.target.value)}
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    >
                                        <option value="user">Usuário</option>
                                        <option value="admin">Admin</option>
                                    </select>
                                </div>
                                <div className="flex gap-3 pt-4">
                                    <button
                                        onClick={() => setInviteModalOpen(false)}
                                        className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        onClick={handleInvite}
                                        className="flex-1 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700"
                                    >
                                        Convidar
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
