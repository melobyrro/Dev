import { useEffect, useState } from 'react';
import { useVideoStore } from '../stores/videoStore';
import { useChatStore } from '../stores/chatStore';
import axios from 'axios';
import { config } from '../lib/config';
import type { VideoDetailedReportDTO } from '../types';

export function VideoDetailDrawer() {
  const { selectedVideoId, setSelectedVideoId } = useVideoStore();
  const { isOpen: chatbotOpen, drawerWidth: chatbotWidth } = useChatStore();
  const [report, setReport] = useState<VideoDetailedReportDTO | null>(null);
  const [transcript, setTranscript] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);
  const [loadingTranscript, setLoadingTranscript] = useState(false);

  useEffect(() => {
    if (selectedVideoId) {
      fetchDetailedReport();
    } else {
      setReport(null);
      setTranscript(null);
      setShowTranscript(false);
    }
  }, [selectedVideoId]);

  const fetchDetailedReport = async () => {
    if (!selectedVideoId) return;

    setLoading(true);
    try {
      const response = await axios.get(
        `${config.apiBaseUrl}/api/v2/videos/${selectedVideoId}/detailed-report`
      );
      if (response.data.success) {
        setReport(response.data.data);
      }
    } catch (error) {
      console.error('Error fetching detailed report:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTranscript = async () => {
    if (!selectedVideoId || transcript) return;

    setLoadingTranscript(true);
    try {
      const response = await axios.get(
        `${config.apiBaseUrl}/api/v2/videos/${selectedVideoId}/transcript`
      );
      if (response.data.success) {
        setTranscript(response.data.data.transcript);
      }
    } catch (error) {
      console.error('Error fetching transcript:', error);
    } finally {
      setLoadingTranscript(false);
    }
  };

  const handleClose = () => {
    setSelectedVideoId(null);
  };

  const toggleTranscript = () => {
    if (!showTranscript && !transcript) {
      fetchTranscript();
    }
    setShowTranscript(!showTranscript);
  };

  if (!selectedVideoId) return null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 z-40 transition-opacity"
        onClick={handleClose}
      />

      {/* Drawer */}
      <div
        className="fixed top-0 h-full w-full md:w-2/3 lg:w-1/2 bg-white dark:bg-gray-900 z-50 shadow-2xl overflow-y-auto"
        style={{
          right: chatbotOpen ? `${chatbotWidth}px` : 0,
          transition: 'right 0.3s ease',
        }}
      >
        {/* Header with close button */}
        <div className="sticky top-0 bg-white dark:bg-gray-900 border-b p-4 flex items-center justify-between z-10">
          <h2 className="text-xl font-bold">Detalhes do Sermão</h2>
          <button onClick={handleClose} className="p-2 hover:bg-gray-100 rounded-lg">
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-6">
          {loading ? (
            <div className="flex items-center justify-center py-12">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-teal-600"></div>
            </div>
          ) : report ? (
            <>
              {/* Video Info */}
              <div>
                <h3 className="text-2xl font-bold mb-2">{report.title}</h3>
                <div className="flex flex-wrap gap-4 text-sm text-gray-600 dark:text-gray-400">
                  <span>{report.statistics.duration_minutes} min</span>
                  <span>{report.statistics.word_count.toLocaleString()} palavras</span>
                  {report.speaker && <span>Pregador: {report.speaker}</span>}
                </div>
              </div>

              {/* AI Summary */}
              {report.ai_summary && (
                <div className="bg-purple-50 dark:bg-purple-900/20 rounded-lg p-4">
                  <h4 className="font-semibold mb-2 text-gray-900 dark:text-white">📝 Resumo do Sermão</h4>
                  <p className="whitespace-pre-line text-gray-700 dark:text-gray-200">{report.ai_summary}</p>
                </div>
              )}

              {/* Themes */}
              {report.themes && report.themes.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-3 text-gray-900 dark:text-white">🎯 Temas Identificados</h4>
                  <div className="flex flex-wrap gap-2">
                    {report.themes.map((theme, idx) => (
                      <span key={idx} className="px-3 py-1 bg-teal-100 dark:bg-teal-900/30 text-teal-800 dark:text-teal-300 rounded-full text-sm border border-teal-300 dark:border-teal-700">
                        {theme.theme} ({Math.round(theme.score * 100)}%)
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Biblical Passages */}
              {report.passages && report.passages.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-3 text-gray-900 dark:text-white">📖 Passagens Bíblicas ({report.passages.length})</h4>
                  <div className="grid grid-cols-2 gap-2">
                    {report.passages.map((passage, idx) => (
                      <div key={idx} className="text-sm bg-gray-50 dark:bg-gray-800 px-2 py-1 rounded">
                        {passage.book} {passage.chapter}:{passage.verse_start}
                        {passage.verse_end && passage.verse_end !== passage.verse_start ? `-${passage.verse_end}` : ''}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Highlights */}
              {report.highlights && report.highlights.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-3 text-gray-900 dark:text-white">⭐ Destaques</h4>
                  <div className="space-y-3">
                    {report.highlights.map((highlight, idx) => (
                      <div key={idx} className="border-l-4 border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20 p-3 rounded">
                        <h5 className="font-semibold mb-1 text-gray-900 dark:text-white">{highlight.title}</h5>
                        <p className="text-sm text-gray-700 dark:text-gray-200">{highlight.summary}</p>
                        {highlight.timestamp && (
                          <span className="text-xs text-gray-500 dark:text-gray-400 mt-1 block">
                            ⏱️ {Math.floor(highlight.timestamp / 60)}:{String(highlight.timestamp % 60).padStart(2, '0')}
                          </span>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Discussion Questions */}
              {report.discussion_questions && report.discussion_questions.length > 0 && (
                <div>
                  <h4 className="font-semibold mb-3 text-gray-900 dark:text-white">💭 Perguntas para Discussão</h4>
                  <div className="space-y-2">
                    {report.discussion_questions.map((q, idx) => (
                      <div key={idx} className="bg-gray-50 dark:bg-gray-800 p-3 rounded">
                        <p className="text-gray-700 dark:text-gray-200">{idx + 1}. {q.question}</p>
                        {q.passage && <span className="text-sm text-teal-600 dark:text-teal-400 mt-1 block">📖 {q.passage}</span>}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Collapsible Transcript */}
              <div>
                <button onClick={toggleTranscript} className="w-full flex items-center justify-between bg-gray-100 dark:bg-gray-800 p-4 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-700">
                  <h4 className="font-semibold text-gray-900 dark:text-white">📄 Transcrição Completa</h4>
                  <svg className={`w-5 h-5 transition-transform ${showTranscript ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </button>

                {showTranscript && (
                  <div className="mt-3 bg-white dark:bg-gray-900 p-4 rounded-lg border border-gray-200 dark:border-gray-700 max-h-96 overflow-y-auto">
                    {loadingTranscript ? (
                      <div className="flex items-center justify-center py-8">
                        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-teal-600"></div>
                      </div>
                    ) : transcript ? (
                      <div className="whitespace-pre-line font-serif leading-relaxed text-justify text-gray-700 dark:text-gray-200">
                        {transcript.split('\n\n').map((para, idx) => (
                          <p key={idx} className="mb-4">{para}</p>
                        ))}
                      </div>
                    ) : (
                      <p className="text-gray-500 dark:text-gray-400">Transcrição não disponível</p>
                    )}
                  </div>
                )}
              </div>
            </>
          ) : (
            <p className="text-center text-gray-500 dark:text-gray-400">Erro ao carregar detalhes</p>
          )}
        </div>
      </div>
    </>
  );
}
