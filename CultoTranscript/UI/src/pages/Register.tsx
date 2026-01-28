import { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { authService } from '../services/authService';

export default function Register() {
    const [searchParams] = useSearchParams();
    const inviteToken = searchParams.get('token') || searchParams.get('invite') || '';
    const [formData, setFormData] = useState({
        email: '',
        password: '',
        church_name: '',
        subdomain: '',
        invite_token: inviteToken,
    });
    const [error, setError] = useState('');
    const [loading, setLoading] = useState(false);

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setFormData({ ...formData, [e.target.name]: e.target.value });
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError('');
        setLoading(true);

        if (!inviteToken) {
            setError('Um convite é obrigatório para criar uma conta. Solicite um convite ao administrador da sua igreja.');
            setLoading(false);
            return;
        }

        try {
            await authService.register(formData);
            // Force a hard reload to ensure session cookies are picked up
            window.location.href = '/admin';
        } catch (err) {
            setError('Erro ao criar conta. Verifique os dados e tente novamente.');
            setLoading(false);
        }
    };

    return (
        <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
            <div className="max-w-md w-full space-y-8">
                <div className="text-center">
                    <h2 className="mt-6 text-3xl font-extrabold text-gray-900 dark:text-white">
                        Criar Conta
                    </h2>
                    <p className="mt-2 text-sm text-gray-600 dark:text-gray-400">
                        Comece a usar o CultoTranscript
                    </p>
                </div>
                {!inviteToken && (
                    <div className="p-4 rounded-lg border border-amber-200 bg-amber-50 text-sm text-amber-900 dark:bg-amber-900/20 dark:border-amber-700 dark:text-amber-100">
                        Você precisa de um link de convite para se registrar. Cole o link recebido ou peça um novo convite ao administrador.
                    </div>
                )}
                {inviteToken && (
                    <div className="p-3 rounded-lg border border-emerald-200 bg-emerald-50 text-sm text-emerald-900 dark:bg-emerald-900/20 dark:border-emerald-700 dark:text-emerald-100">
                        Convite detectado. Complete os dados abaixo para ativar sua conta.
                    </div>
                )}
                <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
                    <div className="rounded-md shadow-sm -space-y-px">
                        <div>
                            <label htmlFor="church_name" className="sr-only">
                                Nome da Igreja
                            </label>
                            <input
                                id="church_name"
                                name="church_name"
                                type="text"
                                required={!inviteToken}
                                disabled={Boolean(inviteToken)}
                                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white dark:bg-gray-800 rounded-t-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
                                placeholder="Nome da Igreja"
                                value={formData.church_name}
                                onChange={handleChange}
                            />
                        </div>
                        <div>
                            <label htmlFor="email-address" className="sr-only">
                                Email
                            </label>
                            <input
                                id="email-address"
                                name="email"
                                type="email"
                                autoComplete="email"
                                required
                                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white dark:bg-gray-800 focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
                                placeholder="Email"
                                value={formData.email}
                                onChange={handleChange}
                            />
                        </div>
                        <div>
                            <label htmlFor="password" className="sr-only">
                                Senha
                            </label>
                            <input
                                id="password"
                                name="password"
                                type="password"
                                autoComplete="new-password"
                                required
                                minLength={8}
                                className="appearance-none rounded-none relative block w-full px-3 py-2 border border-gray-300 dark:border-gray-700 placeholder-gray-500 dark:placeholder-gray-400 text-gray-900 dark:text-white dark:bg-gray-800 rounded-b-md focus:outline-none focus:ring-blue-500 focus:border-blue-500 focus:z-10 sm:text-sm"
                                placeholder="Senha (mínimo 8 caracteres)"
                                value={formData.password}
                                onChange={handleChange}
                            />
                        </div>
                    </div>

                    {error && (
                        <div className="text-red-500 text-sm text-center">{error}</div>
                    )}

                    <div>
                        <button
                            type="submit"
                            disabled={loading}
                            className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50"
                        >
                            {loading ? 'Criando conta...' : 'Criar Conta'}
                        </button>
                    </div>

                    <div className="text-center text-sm">
                        <Link
                            to="/login"
                            className="font-medium text-blue-600 hover:text-blue-500 dark:text-blue-400"
                        >
                            Já tem uma conta? Entre aqui
                        </Link>
                    </div>
                </form>
            </div>
        </div>
    );
}
