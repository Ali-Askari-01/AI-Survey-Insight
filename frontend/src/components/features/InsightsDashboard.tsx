'use client';

import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { clientApi } from '@/lib/clientApi';
import { Loader, TrendingUp, MessageSquare, AlertCircle } from 'lucide-react';

interface InsightData {
  themes: Array<{ theme: string; count: number; sentiment: string }>;
  sentimentTrends: Array<{ question: string; sentiment: string; score: number }>;
  painPoints: Array<{ issue: string; frequency: number; severity: string }>;
  highlights: Array<{ positive: string; count: number }>;
  summary: string;
  recommendations: string[];
}

export default function InsightsPage() {
  const [insights, setInsights] = useState<InsightData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [responseStats, setResponseStats] = useState({ total: 0, positive: 0, neutral: 0, negative: 0 });

  useEffect(() => {
    loadInsights();
  }, []);

  const loadInsights = async () => {
    try {
      const surveys = await clientApi.surveys.list();
      if (surveys && surveys.length > 0) {
        const survey = surveys[0];
        const [summaryData, themeData, patternData] = await Promise.all([
          clientApi.insights.getSummary(survey.id),
          clientApi.insights.getThemes(survey.id),
          clientApi.insights.getPatterns(survey.id),
        ]);

        const sentimentDistribution = Array.isArray(summaryData?.sentiment_distribution)
          ? summaryData.sentiment_distribution
          : [];

        const responseTotal = Number(summaryData?.total_responses || 0);
        const positiveCount = Number(sentimentDistribution.find((s: any) => s.sentiment === 'positive')?.count || 0);
        const neutralCount = Number(sentimentDistribution.find((s: any) => s.sentiment === 'neutral')?.count || 0);
        const negativeCount = Number(sentimentDistribution.find((s: any) => s.sentiment === 'negative')?.count || 0);

        const recurringIssues = Array.isArray(patternData?.recurring_issues) ? patternData.recurring_issues : [];
        const highRiskIssues = Array.isArray(patternData?.high_risk) ? patternData.high_risk : [];
        const opportunities = Array.isArray(patternData?.opportunities) ? patternData.opportunities : [];
        const topInsights = Array.isArray(summaryData?.top_insights) ? summaryData.top_insights : [];

        const mappedInsights: InsightData = {
          themes: (Array.isArray(themeData) ? themeData : []).slice(0, 8).map((theme: any) => ({
            theme: theme.name || 'Untitled theme',
            count: Number(theme.frequency || 0),
            sentiment: Number(theme.sentiment_avg || 0) > 0.2 ? 'positive' : Number(theme.sentiment_avg || 0) < -0.2 ? 'negative' : 'neutral',
          })),
          sentimentTrends: [
            {
              question: 'Positive sentiment share',
              sentiment: 'positive',
              score: responseTotal > 0 ? positiveCount / responseTotal : 0,
            },
            {
              question: 'Neutral sentiment share',
              sentiment: 'neutral',
              score: responseTotal > 0 ? neutralCount / responseTotal : 0,
            },
            {
              question: 'Negative sentiment share',
              sentiment: 'negative',
              score: responseTotal > 0 ? negativeCount / responseTotal : 0,
            },
          ],
          painPoints: [...highRiskIssues, ...recurringIssues].slice(0, 6).map((item: any) => ({
            issue: item.title || item.description || 'Recurring issue',
            frequency: Number(item.frequency || 0),
            severity: Number(item.impact_score || 0) > 0.7 ? 'high' : Number(item.impact_score || 0) > 0.4 ? 'medium' : 'low',
          })),
          highlights: topInsights
            .filter((item: any) => item.sentiment === 'positive')
            .slice(0, 6)
            .map((item: any) => ({
              positive: item.title || item.description || 'Positive feedback',
              count: Number(item.frequency || 0),
            })),
          summary: `Discovered ${Number(summaryData?.total_insights || 0)} insights across ${Number(summaryData?.total_themes || 0)} themes from ${responseTotal} responses.`,
          recommendations: opportunities.slice(0, 5).map((item: any) => item.title || item.description).filter(Boolean),
        };

        if (mappedInsights.recommendations.length === 0) {
          mappedInsights.recommendations = [
            'Prioritize the highest-impact negative themes and validate fixes with follow-up interviews.',
            'Track sentiment trend changes weekly to measure product improvements.',
          ];
        }

        setResponseStats({
          total: responseTotal,
          positive: positiveCount,
          neutral: neutralCount,
          negative: negativeCount,
        });
        setInsights(mappedInsights);
      }
    } catch (error) {
      console.error('Failed to load insights:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader className="w-8 h-8 animate-spin text-cyan-500" />
      </div>
    );
  }

  if (!insights) {
    return (
      <div className="p-6">
        <p className="text-gray-400">No insights available yet. Responses are being analyzed...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Executive Summary */}
      <Card className="border-l-4 border-l-cyan-500">
        <div className="p-6">
          <h2 className="text-2xl font-bold mb-4 flex items-center gap-2">
            <TrendingUp className="w-6 h-6 text-cyan-500" />
            Executive Summary
          </h2>
          <p className="text-gray-300 leading-relaxed">{insights.summary}</p>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Themes */}
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <MessageSquare className="w-5 h-5 text-purple-500" />
              Key Themes
            </h3>
            <div className="space-y-3">
              {insights.themes.slice(0, 5).map((theme, idx) => (
                <div key={idx} className="flex items-center justify-between p-3 bg-gray-800 rounded">
                  <div>
                    <p className="font-semibold text-sm">{theme.theme}</p>
                    <p className="text-xs text-gray-400">Mentioned {theme.count} times</p>
                  </div>
                  <span className={`text-xs px-2 py-1 rounded ${
                    theme.sentiment === 'positive' ? 'bg-green-600/20 text-green-400' :
                    theme.sentiment === 'negative' ? 'bg-red-600/20 text-red-400' :
                    'bg-yellow-600/20 text-yellow-400'
                  }`}>
                    {theme.sentiment}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Sentiment Trends */}
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-semibold mb-4">Sentiment Analysis</h3>
            <div className="space-y-3">
              {insights.sentimentTrends.slice(0, 5).map((trend, idx) => (
                <div key={idx}>
                  <p className="text-sm font-semibold mb-1">{trend.question}</p>
                  <div className="flex items-center gap-2">
                    <div className="flex-1 bg-gray-800 rounded-full h-2">
                      <div
                        className={`h-2 rounded-full ${
                          trend.sentiment === 'positive' ? 'bg-green-500' :
                          trend.sentiment === 'negative' ? 'bg-red-500' :
                          'bg-yellow-500'
                        }`}
                        style={{ width: `${Math.abs(trend.score) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs font-semibold text-gray-400 w-12">
                      {trend.sentiment === 'positive' ? '+' : ''}{(trend.score * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Pain Points */}
        <Card className="border-l-4 border-l-red-500">
          <div className="p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-red-500" />
              Pain Points
            </h3>
            <div className="space-y-2">
              {insights.painPoints.map((point, idx) => (
                <div key={idx} className="p-3 bg-red-600/10 border border-red-600/20 rounded">
                  <p className="font-semibold text-sm">{point.issue}</p>
                  <p className="text-xs text-gray-400 mt-1">
                    Severity: <span className="font-semibold">{point.severity}</span> • Mentioned {point.frequency} times
                  </p>
                </div>
              ))}
            </div>
          </div>
        </Card>

        {/* Highlights */}
        <Card className="border-l-4 border-l-green-500">
          <div className="p-6">
            <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
              <span className="text-green-500">✨</span>
              Positive Highlights
            </h3>
            <div className="space-y-2">
              {insights.highlights.map((highlight, idx) => (
                <div key={idx} className="p-3 bg-green-600/10 border border-green-600/20 rounded">
                  <p className="font-semibold text-sm">{highlight.positive}</p>
                  <p className="text-xs text-gray-400 mt-1">Mentioned {highlight.count} times</p>
                </div>
              ))}
            </div>
          </div>
        </Card>
      </div>

      {/* Recommendations */}
      <Card>
        <div className="p-6">
          <h3 className="text-lg font-semibold mb-4">Recommended Actions</h3>
          <ol className="space-y-3">
            {insights.recommendations.map((rec, idx) => (
              <li key={idx} className="flex gap-3">
                <div className="w-6 h-6 rounded-full bg-cyan-600 flex items-center justify-center text-xs font-bold flex-shrink-0">
                  {idx + 1}
                </div>
                <p className="text-sm text-gray-300">{rec}</p>
              </li>
            ))}
          </ol>
        </div>
      </Card>

      {/* Response Stats */}
      {responseStats.total > 0 && (
        <Card>
          <div className="p-6">
            <h3 className="text-lg font-semibold mb-4">Response Statistics</h3>
            <div className="grid grid-cols-4 gap-4">
              <div className="p-4 bg-gray-800 rounded text-center">
                <p className="text-3xl font-bold text-cyan-500">{responseStats.total}</p>
                <p className="text-xs text-gray-400 mt-1">Total Responses</p>
              </div>
              <div className="p-4 bg-gray-800 rounded text-center">
                <p className="text-3xl font-bold text-green-500">{responseStats.positive}</p>
                <p className="text-xs text-gray-400 mt-1">Positive</p>
              </div>
              <div className="p-4 bg-gray-800 rounded text-center">
                <p className="text-3xl font-bold text-yellow-500">{responseStats.neutral}</p>
                <p className="text-xs text-gray-400 mt-1">Neutral</p>
              </div>
              <div className="p-4 bg-gray-800 rounded text-center">
                <p className="text-3xl font-bold text-red-500">{responseStats.negative}</p>
                <p className="text-xs text-gray-400 mt-1">Negative</p>
              </div>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
