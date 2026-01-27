import { useJobStore } from '../stores/jobStore';

export function ProgressModal() {
    const { jobs, isModalOpen, setModalOpen, clearCompleted } = useJobStore();

    if (!isModalOpen || jobs.size === 0) return null;

    const jobsArray = Array.from(jobs.values());
    const processingCount = jobsArray.filter(j => j.status === 'processing' || j.status === 'queued').length;
    const completedCount = jobsArray.filter(j => j.status === 'completed' || j.status === 'failed').length;

    return (
        <>
            {/* Backdrop */}
            <div
                className="fixed inset-0 bg-black bg-opacity-25 z-40"
                onClick={() => setModalOpen(false)}
            />

            {/* Modal */}
            <div className="fixed bottom-4 right-4 w-96 bg-white dark:bg-gray-800 rounded-lg shadow-2xl z-50 max-h-96 flex flex-col">
                {/* Header */}
                <div className="flex items-center justify-between p-4 border-b dark:border-gray-700">
                    <h3 className="font-semibold text-gray-900 dark:text-white">
                        Processamento ({processingCount} em andamento)
                    </h3>
                    <div className="flex gap-2">
                        {completedCount > 0 && (
                            <button
                                onClick={clearCompleted}
                                className="text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
                            >
                                Limpar
                            </button>
                        )}
                        <button onClick={() => setModalOpen(false)} className="text-gray-500 hover:text-gray-700 dark:hover:text-gray-300">
                            ✕
                        </button>
                    </div>
                </div>

                {/* Jobs list */}
                <div className="overflow-y-auto flex-1 p-2">
                    {jobsArray.map(job => (
                        <div key={job.jobId} className="p-3 bg-gray-50 dark:bg-gray-700 rounded mb-2">
                            <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium truncate flex-1 text-gray-900 dark:text-white">
                                    {job.videoTitle}
                                </span>
                                <StatusBadge status={job.status} />
                            </div>

                            {(job.status === 'processing' || job.status === 'queued') && (
                                <div className="w-full bg-gray-200 dark:bg-gray-600 rounded-full h-2 mt-2">
                                    <div
                                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                                        style={{ width: `${job.progress}%` }}
                                    />
                                </div>
                            )}

                            {job.message && (
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{job.message}</p>
                            )}
                        </div>
                    ))}
                </div>
            </div>
        </>
    );
}

function StatusBadge({ status }: { status: string }) {
    const styles: Record<string, string> = {
        queued: 'bg-gray-100 text-gray-800 dark:bg-gray-600 dark:text-gray-200',
        processing: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
        completed: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
        failed: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    };
    const labels: Record<string, string> = {
        queued: 'Na fila',
        processing: 'Processando',
        completed: 'Concluído',
        failed: 'Falhou',
    };
    return (
        <span className={`px-2 py-0.5 text-xs rounded-full ${styles[status]}`}>
            {labels[status]}
        </span>
    );
}
