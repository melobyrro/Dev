import { useState, useEffect } from 'react';
import axios from 'axios';
import { useVideoStore } from '../stores/videoStore';

interface Member {
    id: number;
    email: string;
    role: string;
    last_login: string | null;
    login_count: number;
}

export default function Admin() {
    const { selectedChannelId, channels, fetchChannels } = useVideoStore();
    const [members, setMembers] = useState<Member[]>([]);
    const [channelData, setChannelData] = useState<any>(null);

    const normalizeTime = (time: string | null | undefined) => {
        const match = (time || '').match(/^(\\d{1,2}):(\\d{2})/);
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

    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        fetchChannels();
    }, []);

    useEffect(() => {
        // Wait for both selectedChannelId AND channels to be available
        if (selectedChannelId && channels.length > 0) {
            loadAdminData();
        }
    }, [selectedChannelId, channels]);

    const loadAdminData = async () => {
        setLoading(true);
        try {
            // Fetch selected channel data from store (always available)
            const channel = channels.find(c => c.id.toString() === selectedChannelId);
            if (channel) {
                setChannelData(channel);
                setYoutubeUrl(channel.youtube_url || '');
                setDefaultSpeaker(channel.default_speaker || '');
            }

            // Fetch members scoped to the selected church (may not exist yet)
            try {
                const membersRes = await axios.get('/api/church/members', {
                    params: selectedChannelId ? { channel_id: selectedChannelId } : undefined,
                });
                setMembers(membersRes.data.members || []);
            } catch (membersError) {
                console.warn('Members endpoint not available:', membersError);
                setMembers([]);
            }

            // Fetch schedule config (must pass channel_id explicitly)
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

    const formatLastLogin = (dateStr: string | null) => {
        if (!dateStr) return 'Nunca';
        const date = new Date(dateStr);
        return date.toLocaleString('pt-BR');
    };

    const dayNames = ['Segunda', 'Terça', 'Quarta', 'Quinta', 'Sexta', 'Sábado', 'Domingo'];

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    return (
        <div className="max-w-6xl mx-auto p-6 space-y-8">
            <h1 className="text-3xl font-bold mb-6 text-gray-900 dark:text-white">Administração - {channelData?.title || 'Carregando...'}</h1>

            {/* Channel Configuration */}
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-gray-900 dark:text-white">
                    📺 Configuração do Canal
                </h2>
                <div className="space-y-4">
                    <div>
                        <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-200">Link do Canal do YouTube</label>
                        <input
                            type="url"
                            value={youtubeUrl}
                            onChange={(e) => setYoutubeUrl(e.target.value)}
                            placeholder="https://www.youtube.com/@seucanal"
                            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                            Atual: {channelData?.youtube_url || 'Não configurado'}
                        </p>
                    </div>
                    <div>
                        <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-200">Pregador padrão</label>
                        <input
                            type="text"
                            value={defaultSpeaker}
                            onChange={(e) => setDefaultSpeaker(e.target.value)}
                            placeholder="Nome do pregador padrão"
                            className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                            Usado quando um pregador não é detectado automaticamente.
                        </p>
                    </div>
                    <button
                        onClick={handleSaveChannel}
                        disabled={saving}
                        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {saving ? 'Salvando...' : 'Salvar Configuração'}
                    </button>
                </div>
            </div>

            {/* Automatic Scheduling */}
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-gray-900 dark:text-white">
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
                        <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-200">Horário de Execução</label>
                        <input
                            type="time"
                            value={scheduleTime}
                            onChange={(e) => setScheduleTime(e.target.value)}
                            className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                        />
                    </div>

                    <div>
                        <label className="block text-sm font-medium mb-2 text-gray-700 dark:text-gray-200">Dia da Semana</label>
                        <div className="grid grid-cols-7 gap-2">
                            {dayNames.map((day, idx) => (
                                <button
                                    key={idx}
                                    onClick={() => setScheduleDay(idx)}
                                    className={`px-3 py-2 text-sm rounded-lg border transition-colors ${scheduleDay === idx
                                        ? 'bg-blue-600 text-white border-blue-600'
                                        : 'bg-white dark:bg-gray-700 border-gray-300 dark:border-gray-600 hover:border-blue-400'
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
                        className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                    >
                        {saving ? 'Salvando...' : 'Atualizar Agendamento'}
                    </button>
                </div>
            </div>

            {/* Members and Access */}
            <div className="bg-white dark:bg-gray-800 rounded-lg p-6 shadow-sm">
                <h2 className="text-xl font-semibold mb-4 flex items-center gap-2 text-gray-900 dark:text-white">
                    👥 Membros e Acesso
                </h2>
                <div className="overflow-x-auto">
                    <table className="w-full">
                        <thead>
                            <tr className="border-b border-gray-200 dark:border-gray-700">
                                <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-white">Email</th>
                                <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-white">Perfil</th>
                                <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-white">Último Login</th>
                                <th className="text-left py-3 px-4 font-medium text-gray-700 dark:text-white">Total Logins</th>
                            </tr>
                        </thead>
                        <tbody>
                            {members.map((member) => (
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
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
                <button className="mt-4 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors">
                    Convidar Novo Membro
                </button>
            </div>
        </div>
    );
}
