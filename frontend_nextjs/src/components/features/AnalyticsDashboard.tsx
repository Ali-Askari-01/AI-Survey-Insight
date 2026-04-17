'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { clientApi } from '@/lib/clientApi';
import { BarChart3, PieChart as PieChartIcon, TrendingUp, Users } from 'lucide-react';

export default function AnalyticsDashboard() {
  const [surveyStats, setSurveyStats] = useState<any>(null);
  const [coverageSeries, setCoverageSeries] = useState<Array<{ label: string; value: number }>>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadAnalytics();
  }, []);

  const loadAnalytics = async () => {
    try {
      const surveys = await clientApi.surveys.list();
      if (surveys && surveys.length > 0) {
        const stats = await clientApi.publish.analytics(surveys[0].id);
        setSurveyStats(stats);

        const questionStats = Array.isArray(stats?.question_stats) ? stats.question_stats : [];
        setCoverageSeries(
          questionStats.slice(0, 7).map((item: any, index: number) => ({
            label: `Q${index + 1}`,
            value: Number(item.response_count || 0),
          }))
        );
      }
    } catch (error) {
      console.error('Failed to load analytics:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return <div className="p-6">Loading analytics...</div>;
  }

  if (!surveyStats) {
    return <div className="p-6 text-gray-400">No analytics available yet. Publish a survey and collect responses to see metrics.</div>;
  }

  const channelBreakdown = Array.isArray(surveyStats?.channel_breakdown)
    ? surveyStats.channel_breakdown.reduce((acc: Record<string, number>, item: any) => {
        const channel = String(item.channel || '').toLowerCase();
        if (!channel) return acc;
        acc[channel] = Number(item.count || 0);
        return acc;
      }, {})
    : {};

  const avgSentiment = Number(surveyStats?.avg_sentiment);
  const avgSentimentPct = Number.isFinite(avgSentiment)
    ? Math.round(((avgSentiment + 1) / 2) * 100)
    : 0;
  const avgEngagement = Number(surveyStats?.session_stats?.avg_engagement);
  const avgEngagementPct = Number.isFinite(avgEngagement)
    ? Math.round(avgEngagement * 100)
    : 0;
  const maxCoverage = Math.max(...coverageSeries.map(item => item.value), 1);

  return (
    <div className="space-y-6">
      {/* KPIs */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm text-gray-400">Total Responses</h3>
              <Users className="w-5 h-5 text-cyan-500" />
            </div>
            <p className="text-3xl font-bold">{surveyStats?.total_respondents || 0}</p>
            <p className="text-xs text-gray-400 mt-2">+12% from last week</p>
          </div>
        </Card>

        <Card>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm text-gray-400">Completion Rate</h3>
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
            <p className="text-3xl font-bold">{surveyStats?.completion_rate || 0}%</p>
            <p className="text-xs text-gray-400 mt-2">Excellent engagement</p>
          </div>
        </Card>

        <Card>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm text-gray-400">Avg. Duration</h3>
              <BarChart3 className="w-5 h-5 text-purple-500" />
            </div>
            <p className="text-3xl font-bold">{avgEngagementPct}%</p>
            <p className="text-xs text-gray-400 mt-2">Average engagement</p>
          </div>
        </Card>

        <Card>
          <div className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm text-gray-400">Sentiment</h3>
              <PieChartIcon className="w-5 h-5 text-yellow-500" />
            </div>
            <p className="text-3xl font-bold">{avgSentimentPct}%</p>
            <p className="text-xs text-gray-400 mt-2">Overall positive</p>
          </div>
        </Card>
      </div>

      {/* Response Trend */}
      <Card>
        <div className="p-6">
          <h3 className="text-lg font-semibold mb-4">Question Response Coverage</h3>
          <div className="space-y-2">
            {coverageSeries.length > 0 ? coverageSeries.map((item) => (
              <div key={item.label} className="flex items-center gap-3">
                <span className="text-xs text-gray-400 w-12">{item.label}</span>
                <div className="flex-1 h-8 bg-gray-800 rounded flex items-center">
                  <div
                    className="h-8 bg-gradient-to-r from-cyan-500 to-purple-600 rounded"
                    style={{ width: `${Math.max(8, (item.value / maxCoverage) * 100)}%` }}
                  />
                </div>
                <span className="text-xs text-gray-400 w-8 text-right">{item.value}</span>
              </div>
            )) : <p className="text-sm text-gray-400">No response coverage data available yet.</p>}
          </div>
        </div>
      </Card>

      {/* Demographics */}
      <Card>
        <div className="p-6">
          <h3 className="text-lg font-semibold mb-4">Response Demographics</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 bg-gray-800 rounded">
              <p className="text-sm text-gray-400 mb-1">Web Form</p>
              <p className="text-2xl font-bold">{channelBreakdown.web || 0}</p>
            </div>
            <div className="p-4 bg-gray-800 rounded">
              <p className="text-sm text-gray-400 mb-1">Chat</p>
              <p className="text-2xl font-bold">{channelBreakdown.chat || 0}</p>
            </div>
            <div className="p-4 bg-gray-800 rounded">
              <p className="text-sm text-gray-400 mb-1">Voice</p>
              <p className="text-2xl font-bold">{(channelBreakdown.audio || channelBreakdown.voice || 0)}</p>
            </div>
            <div className="p-4 bg-gray-800 rounded">
              <p className="text-sm text-gray-400 mb-1">Completed</p>
              <p className="text-2xl font-bold">{surveyStats?.completed || 0}</p>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
