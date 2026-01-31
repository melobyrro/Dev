import { useState, useEffect } from 'react';
import axios from 'axios';

export default function Settings() {
    const [userEmail, setUserEmail] = useState('');
    const [loading, setLoading] = useState(true);

    // Password change state
    const [showPasswordForm, setShowPasswordForm] = useState(false);
    const [currentPassword, setCurrentPassword] = useState('');
    const [newPassword, setNewPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [passwordError, setPasswordError] = useState('');
    const [passwordSuccess, setPasswordSuccess] = useState(false);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        loadUserProfile();
    }, []);

    const loadUserProfile = async () => {
        try {
            const res = await axios.get('/api/user/profile');
            if (res.data.success) {
                setUserEmail(res.data.data.email);
            }
        } catch (error) {
            console.error('Error loading user profile:', error);
        } finally {
            setLoading(false);
        }
    };

    const handlePasswordChange = async () => {
        setPasswordError('');
        setPasswordSuccess(false);

        if (!currentPassword || !newPassword || !confirmPassword) {
            setPasswordError('Preencha todos os campos');
            return;
        }

        if (newPassword.length < 6) {
            setPasswordError('A nova senha deve ter pelo menos 6 caracteres');
            return;
        }

        if (newPassword !== confirmPassword) {
            setPasswordError('As senhas não coincidem');
            return;
        }

        setSaving(true);
        try {
            const res = await axios.post('/api/user/change-password', {
                current_password: currentPassword,
                new_password: newPassword,
            });
            if (res.data.success) {
                setPasswordSuccess(true);
                setCurrentPassword('');
                setNewPassword('');
                setConfirmPassword('');
                setTimeout(() => {
                    setShowPasswordForm(false);
                    setPasswordSuccess(false);
                }, 2000);
            } else {
                setPasswordError(res.data.message || 'Erro ao alterar senha');
            }
        } catch (error: any) {
            setPasswordError(error.response?.data?.message || 'Erro ao alterar senha');
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="flex items-center justify-center py-12">
                <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            </div>
        );
    }

    return (
        <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">
                Configurações
            </h1>

            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
                <div className="p-6 space-y-8">
                    {/* Profile Section */}
                    <section>
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                            Perfil
                        </h2>
                        <div className="space-y-4">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                    Email
                                </label>
                                <div className="text-gray-900 dark:text-white bg-gray-50 dark:bg-gray-700/50 px-4 py-2 rounded-lg">
                                    {userEmail}
                                </div>
                            </div>
                        </div>
                    </section>

                    <hr className="border-gray-200 dark:border-gray-700" />

                    {/* Password Section */}
                    <section>
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                            Segurança
                        </h2>

                        {!showPasswordForm ? (
                            <button
                                onClick={() => setShowPasswordForm(true)}
                                className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
                            >
                                Alterar Senha
                            </button>
                        ) : (
                            <div className="space-y-4 max-w-md">
                                {passwordSuccess && (
                                    <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 text-green-800 dark:text-green-300 px-4 py-3 rounded-lg">
                                        Senha alterada com sucesso!
                                    </div>
                                )}

                                {passwordError && (
                                    <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-red-800 dark:text-red-300 px-4 py-3 rounded-lg">
                                        {passwordError}
                                    </div>
                                )}

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Senha Atual
                                    </label>
                                    <input
                                        type="password"
                                        value={currentPassword}
                                        onChange={(e) => setCurrentPassword(e.target.value)}
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Nova Senha
                                    </label>
                                    <input
                                        type="password"
                                        value={newPassword}
                                        onChange={(e) => setNewPassword(e.target.value)}
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    />
                                </div>

                                <div>
                                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                                        Confirmar Nova Senha
                                    </label>
                                    <input
                                        type="password"
                                        value={confirmPassword}
                                        onChange={(e) => setConfirmPassword(e.target.value)}
                                        className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                                    />
                                </div>

                                <div className="flex gap-3 pt-2">
                                    <button
                                        onClick={() => {
                                            setShowPasswordForm(false);
                                            setPasswordError('');
                                            setCurrentPassword('');
                                            setNewPassword('');
                                            setConfirmPassword('');
                                        }}
                                        className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700"
                                    >
                                        Cancelar
                                    </button>
                                    <button
                                        onClick={handlePasswordChange}
                                        disabled={saving}
                                        className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                                    >
                                        {saving ? 'Salvando...' : 'Salvar Nova Senha'}
                                    </button>
                                </div>
                            </div>
                        )}
                    </section>

                    <hr className="border-gray-200 dark:border-gray-700" />

                    {/* Preferences Section */}
                    <section>
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                            Preferências
                        </h2>
                        <div className="flex items-center justify-between">
                            <span className="text-gray-700 dark:text-gray-300">Tema</span>
                            <span className="text-sm text-gray-500 dark:text-gray-400">
                                Use o botão no menu superior para alternar entre claro e escuro
                            </span>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}
