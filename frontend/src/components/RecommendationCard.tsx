import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { recommendationsApi } from '../services/api';
import { toast } from 'react-hot-toast';

interface Recommendation {
  title: string;
  author: string;
  description: string;
  rss_url: string;
  artwork_url: string;
  reason: string;
}

interface Props {
  onSubscribed: () => void;
}

export default function RecommendationCard({ onSubscribed }: Props) {
  const queryClient = useQueryClient();

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ['recommendation'],
    queryFn: recommendationsApi.getRecommendation,
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  const dismissMutation = useMutation({
    mutationFn: (rec: Recommendation) =>
      recommendationsApi.dismissRecommendation(rec.title, rec.rss_url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['recommendation'] });
    },
    onError: () => toast.error('Failed to dismiss recommendation'),
  });

  const subscribeMutation = useMutation({
    mutationFn: async (rec: Recommendation) => {
      const formData = new FormData();
      formData.append('url', rec.rss_url);
      await fetch('/feed', { method: 'POST', body: formData, credentials: 'include' });
    },
    onSuccess: (_data, rec) => {
      toast.success(`Subscribed to "${rec.title}"`);
      queryClient.invalidateQueries({ queryKey: ['feeds'] });
      queryClient.invalidateQueries({ queryKey: ['recommendation'] });
      onSubscribed();
    },
    onError: () => toast.error('Failed to subscribe'),
  });

  if (isLoading) {
    return (
      <div className="mb-4 p-4 rounded-xl border border-blue-100 dark:border-blue-900 bg-blue-50 dark:bg-blue-950/30 animate-pulse">
        <div className="h-4 w-48 bg-blue-200 dark:bg-blue-800 rounded mb-2" />
        <div className="h-3 w-full bg-blue-100 dark:bg-blue-900 rounded" />
      </div>
    );
  }

  if (isError || !data?.recommendation) return null;

  const rec = data.recommendation as Recommendation;

  return (
    <div className="mb-4 rounded-xl border border-blue-200 dark:border-blue-800 bg-gradient-to-r from-blue-50 to-indigo-50 dark:from-blue-950/40 dark:to-indigo-950/40 shadow-sm overflow-hidden">
      <div className="px-4 py-3 flex items-center gap-1.5 border-b border-blue-100 dark:border-blue-900">
        <svg className="w-3.5 h-3.5 text-blue-500 dark:text-blue-400 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
          <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
        </svg>
        <span className="text-xs font-semibold text-blue-600 dark:text-blue-400 uppercase tracking-wide">
          Recommended for you
        </span>
      </div>

      <div className="p-4 flex gap-3">
        {rec.artwork_url && (
          <img
            src={rec.artwork_url}
            alt={rec.title}
            className="w-16 h-16 rounded-lg object-cover flex-shrink-0 shadow-sm"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        )}

        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-gray-900 dark:text-white text-sm leading-snug truncate">
            {rec.title}
          </h3>
          {rec.author && (
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 truncate">{rec.author}</p>
          )}
          <p className="text-xs text-blue-700 dark:text-blue-300 mt-1.5 italic leading-relaxed line-clamp-2">
            "{rec.reason}"
          </p>
        </div>
      </div>

      <div className="px-4 pb-3 flex items-center gap-2">
        <button
          onClick={() => subscribeMutation.mutate(rec)}
          disabled={subscribeMutation.isPending}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-md bg-blue-600 hover:bg-blue-700 disabled:opacity-50 text-white text-xs font-medium transition-colors"
        >
          {subscribeMutation.isPending ? (
            <span className="animate-spin rounded-full h-3 w-3 border-b border-white" />
          ) : (
            <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
          )}
          Subscribe
        </button>

        <button
          onClick={() => dismissMutation.mutate(rec)}
          disabled={dismissMutation.isPending}
          className="px-3 py-1.5 rounded-md border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 text-xs font-medium transition-colors"
        >
          Dismiss
        </button>

        <button
          onClick={() => refetch()}
          className="px-3 py-1.5 rounded-md border border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 text-xs font-medium transition-colors"
          title="Get another recommendation"
        >
          <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
      </div>
    </div>
  );
}
