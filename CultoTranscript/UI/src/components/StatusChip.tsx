import { VideoStatus } from '../types';

interface StatusChipProps {
  status: VideoStatus;
}

const statusConfig = {
  [VideoStatus.PROCESSED]: {
    bgColor: 'bg-green-100 dark:bg-green-900/30',
    textColor: 'text-green-800 dark:text-green-300',
    icon: '✅',
    label: 'Processado',
  },
  [VideoStatus.PROCESSING]: {
    bgColor: 'bg-amber-100 dark:bg-amber-900/30',
    textColor: 'text-amber-800 dark:text-amber-300',
    icon: '⏳',
    label: 'Processando',
  },
  [VideoStatus.FAILED]: {
    bgColor: 'bg-red-100 dark:bg-red-900/30',
    textColor: 'text-red-800 dark:text-red-300',
    icon: '❌',
    label: 'Falhou',
  },
  [VideoStatus.PENDING]: {
    bgColor: 'bg-gray-100 dark:bg-gray-800',
    textColor: 'text-gray-800 dark:text-gray-300',
    icon: '⏸️',
    label: 'Pendente',
  },
  [VideoStatus.QUEUED]: {
    bgColor: 'bg-blue-100 dark:bg-blue-900/30',
    textColor: 'text-blue-800 dark:text-blue-300',
    icon: '📋',
    label: 'Na Fila',
  },
};

export default function StatusChip({ status }: StatusChipProps) {
  const config = statusConfig[status];

  return (
    <span
      data-testid="status-chip"
      className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium ${config.bgColor} ${config.textColor}`}
    >
      <span className="text-sm" role="img" aria-label={config.label}>
        {config.icon}
      </span>
      <span>{config.label}</span>
    </span>
  );
}
