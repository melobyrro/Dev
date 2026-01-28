

export default function Settings() {
    return (
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
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
                        <div className="grid grid-cols-1 gap-6 sm:grid-cols-2">
                            <div>
                                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">
                                    Email
                                </label>
                                <div className="mt-1 text-gray-900 dark:text-white">
                                    user@example.com {/* Placeholder - needs user store */}
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
                        <button className="px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-700">
                            Alterar Senha
                        </button>
                    </section>

                    <hr className="border-gray-200 dark:border-gray-700" />

                    {/* Preferences Section */}
                    <section>
                        <h2 className="text-lg font-medium text-gray-900 dark:text-white mb-4">
                            Preferências
                        </h2>
                        <div className="flex items-center justify-between">
                            <span className="text-gray-700 dark:text-gray-300">Tema Escuro</span>
                            {/* Theme toggle is already in TopAppBar, but could be here too */}
                            <span className="text-sm text-gray-500">Gerenciado no menu superior</span>
                        </div>
                    </section>
                </div>
            </div>
        </div>
    );
}
