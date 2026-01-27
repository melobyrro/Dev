import { create } from 'zustand';

export interface TrackedJob {
    jobId: number;
    videoId: string;
    videoTitle: string;
    status: 'queued' | 'processing' | 'completed' | 'failed';
    progress: number;
    message?: string;
    startedAt: Date;
}

interface JobStore {
    jobs: Map<number, TrackedJob>;
    isModalOpen: boolean;

    addJob: (job: TrackedJob) => void;
    updateJob: (jobId: number, updates: Partial<TrackedJob>) => void;
    updateJobByVideoId: (videoId: string, updates: Partial<TrackedJob>) => void;
    removeJob: (jobId: number) => void;
    clearCompleted: () => void;
    setModalOpen: (open: boolean) => void;
}

export const useJobStore = create<JobStore>((set) => ({
    jobs: new Map(),
    isModalOpen: false,

    addJob: (job) => set((state) => {
        const newJobs = new Map(state.jobs);
        newJobs.set(job.jobId, job);
        return { jobs: newJobs, isModalOpen: true };
    }),

    updateJob: (jobId, updates) => set((state) => {
        const newJobs = new Map(state.jobs);
        const existing = newJobs.get(jobId);
        if (existing) {
            newJobs.set(jobId, { ...existing, ...updates });
        }
        return { jobs: newJobs };
    }),

    updateJobByVideoId: (videoId, updates) => set((state) => {
        const newJobs = new Map(state.jobs);
        for (const [jobId, job] of newJobs) {
            if (job.videoId === videoId) {
                newJobs.set(jobId, { ...job, ...updates });
                break;
            }
        }
        return { jobs: newJobs };
    }),

    removeJob: (jobId) => set((state) => {
        const newJobs = new Map(state.jobs);
        newJobs.delete(jobId);
        return { jobs: newJobs };
    }),

    clearCompleted: () => set((state) => {
        const newJobs = new Map(state.jobs);
        for (const [jobId, job] of newJobs) {
            if (job.status === 'completed' || job.status === 'failed') {
                newJobs.delete(jobId);
            }
        }
        return { jobs: newJobs, isModalOpen: newJobs.size > 0 };
    }),

    setModalOpen: (open) => set({ isModalOpen: open }),
}));
