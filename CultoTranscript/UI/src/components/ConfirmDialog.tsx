import { useState } from 'react';

interface ConfirmDialogProps {
    isOpen: boolean;
    title: string;
    message: string;
    confirmLabel?: string;
    cancelLabel?: string;
    variant?: 'danger' | 'warning' | 'default';
    requirePassword?: boolean;
    onConfirm: (password?: string) => void;
    onCancel: () => void;
}

export function ConfirmDialog({
    isOpen,
    title,
    message,
    confirmLabel = 'Confirmar',
    cancelLabel = 'Cancelar',
    variant = 'default',
    requirePassword = false,
    onConfirm,
    onCancel
}: ConfirmDialogProps) {
    const [password, setPassword] = useState('');

    if (!isOpen) return null;

    const handleConfirm = () => {
        onConfirm(requirePassword ? password : undefined);
        setPassword('');
    };

    const handleCancel = () => {
        onCancel();
        setPassword('');
    };

    const variantStyles = {
        danger: 'bg-red-600 hover:bg-red-700',
        warning: 'bg-yellow-600 hover:bg-yellow-700',
        default: 'bg-blue-600 hover:bg-blue-700'
    };

    return (
        <>
            {/* Backdrop */}
            <div className="fixed inset-0 bg-black bg-opacity-50 z-50" onClick={handleCancel} />

            {/* Dialog */}
            <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-md w-full p-6">
                    <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
                        {title}
                    </h3>
                    <p className="text-gray-600 dark:text-gray-300 mb-4">
                        {message}
                    </p>

                    {requirePassword && (
                        <input
                            type="password"
                            placeholder="Senha de administrador"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            className="w-full px-3 py-2 border rounded-lg mb-4 dark:bg-gray-700 dark:border-gray-600 dark:text-white"
                            autoFocus
                        />
                    )}

                    <div className="flex justify-end gap-3">
                        <button
                            onClick={handleCancel}
                            className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg"
                        >
                            {cancelLabel}
                        </button>
                        <button
                            onClick={handleConfirm}
                            disabled={requirePassword && !password}
                            className={`px-4 py-2 text-white rounded-lg disabled:opacity-50 ${variantStyles[variant]}`}
                        >
                            {confirmLabel}
                        </button>
                    </div>
                </div>
            </div>
        </>
    );
}
