'use client';

import { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Input } from '@/components/ui/Input';
import { clientApi } from '@/lib/clientApi';
import { ChevronRight, ChevronLeft, Loader, MessageCircle, Sparkles, Check } from 'lucide-react';

interface Question {
  id?: string;
  question_text: string;
  question_type: string;
  follow_ups: string[];
  tone: string;
  depth: number;
}

export default function SurveyDesigner() {
  const router = useRouter();
  const [currentStep, setCurrentStep] = useState(0);
  const [surveyTitle, setSurveyTitle] = useState('');
  const [goalText, setGoalText] = useState('');
  const [analyzedGoal, setAnalyzedGoal] = useState('');
  const [interviewDuration, setInterviewDuration] = useState(15);
  const [interviewStyle, setInterviewStyle] = useState<'deep' | 'balanced' | 'fast'>('balanced');
  const [includeConsent, setIncludeConsent] = useState(false);
  
  const [intakeConversation, setIntakeConversation] = useState<Array<{ role: string; message: string }>>([]);
  const [isLoadingAI, setIsLoadingAI] = useState(false);
  const [isPublishing, setIsPublishing] = useState(false);
  const [deepResult, setDeepResult] = useState<any>(null);
  const [questions, setQuestions] = useState<Question[]>([]);
  const [survey, setSurvey] = useState<any>(null);
  const [consentForm, setConsentForm] = useState('');
  
  const goalInputRef = useRef<HTMLTextAreaElement>(null);
  const conversationEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    conversationEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [intakeConversation]);

  const steps = ['Describe Your Survey', 'Review Questions', 'Interview Briefing', 'Launch'];

  const handleAnalyzeGoal = async () => {
    if (!goalText.trim() || !surveyTitle.trim()) {
      alert('Please enter both title and goal');
      return;
    }

    setIsLoadingAI(true);
    try {
      // Add user message to conversation
      const newConversation = [...intakeConversation, { role: 'user', message: goalText }];
      setIntakeConversation(newConversation);

      // Call API to clarify
      const clarification = await clientApi.surveys.intakeClarify(goalText, newConversation);

      if (!clarification.has_enough_info) {
        // AI needs more info
        setIntakeConversation([...newConversation, { role: 'ai', message: clarification.ai_message }]);
        setGoalText('');
        return;
      }

      // Generate questions
      await clientApi.surveys.parseGoal(goalText);
      const deep = await clientApi.surveys.generateDeepQuestions(
        goalText,
        'discovery',
        8
      );

      setDeepResult(deep);
      setQuestions(deep.questions || []);
      
      // Create survey in DB
      const goal = await clientApi.surveys.createGoal({
        title: surveyTitle,
        description: goalText,
        research_type: 'discovery',
      });

      const newSurvey = await clientApi.surveys.create({
        title: surveyTitle,
        description: goalText,
        research_goal_id: goal.id,
        channel_type: 'multi',
        estimated_duration: interviewDuration,
        interview_style: interviewStyle,
      });

      setSurvey(newSurvey);
      setAnalyzedGoal(goalText);

      // Save questions
      for (let i = 0; i < deep.questions.length; i++) {
        const q = deep.questions[i];
        await clientApi.surveys.createQuestion({
          survey_id: newSurvey.id,
          question_text: q.question_text,
          question_type: q.question_type || 'open_ended',
          order_index: i,
          is_required: true,
          follow_up_seeds: JSON.stringify(q.follow_ups || []),
          tone: q.tone || 'neutral',
          depth_level: q.depth || 1,
          audience_tag: 'general',
        });
      }

      if (includeConsent) {
        const consent = await clientApi.surveys.generateConsent(surveyTitle, goalText);
        setConsentForm(consent?.consent_form || '');
      } else {
        setConsentForm('');
      }

      setIntakeConversation([
        ...newConversation,
        {
          role: 'ai',
          message: includeConsent
            ? `✅ Analysis complete! I've generated ${deep.questions.length} targeted questions, follow-ups, and a consent form.`
            : `✅ Analysis complete! I've generated ${deep.questions.length} targeted questions with follow-ups.`,
        },
      ]);
      setGoalText('');
      setCurrentStep(1);
    } catch (error) {
      console.error('Error in survey analysis:', error);
      alert('Failed to analyze goal. Please try again.');
    } finally {
      setIsLoadingAI(false);
    }
  };

  const handleLaunch = async (channel: string) => {
    if (!survey) return;

    setIsPublishing(true);
    try {
      const channelFlags = {
        'web-form': { web_form_enabled: true, chat_enabled: false, audio_enabled: false },
        chat: { web_form_enabled: false, chat_enabled: true, audio_enabled: false },
        voice: { web_form_enabled: false, chat_enabled: false, audio_enabled: true },
      }[channel] || { web_form_enabled: true, chat_enabled: true, audio_enabled: true };

      await clientApi.publish.publish({
        survey_id: survey.id,
        title: surveyTitle,
        description: analyzedGoal,
        max_responses: 0,
        require_email: true,
        consent_form_text: includeConsent ? consentForm : '',
        ...channelFlags,
      });

      router.push('/app/surveys');
    } catch (error) {
      console.error('Error launching survey:', error);
      alert('Failed to launch survey.');
    } finally {
      setIsPublishing(false);
    }
  };

  const renderStepContent = () => {
    switch (currentStep) {
      case 0: // Intake
        return (
          <div className="space-y-6">
            {/* Setup Card */}
            <Card className="border-l-4 border-l-cyan-500">
              <div className="p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <Sparkles className="w-5 h-5 text-cyan-500" />
                  Survey Setup
                </h3>
                
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm font-semibold mb-2">
                      Survey Title <span className="text-red-500">*</span>
                    </label>
                    <Input
                      placeholder="e.g. DYHE Course Experience Survey"
                      value={surveyTitle}
                      onChange={(e) => setSurveyTitle(e.target.value)}
                      maxLength={120}
                    />
                    <p className="text-xs text-gray-400 mt-1">This will be shown to respondents.</p>
                  </div>

                  <div>
                    <label className="text-sm font-semibold mb-2 flex items-center gap-2">
                      <span>⏱️</span> Interview Duration (minutes)
                    </label>
                    <div className="flex gap-4 items-center">
                      <input
                        type="range"
                        min="5"
                        max="60"
                        step="5"
                        value={interviewDuration}
                        onChange={(e) => setInterviewDuration(parseInt(e.target.value))}
                        className="flex-1"
                      />
                      <span className="text-lg font-bold text-cyan-500 min-w-12">{interviewDuration} min</span>
                    </div>
                    <p className="text-xs text-gray-400 mt-2">AI will adapt questions to fit this timeframe.</p>
                  </div>

                  <div>
                    <label className="block text-sm font-semibold mb-2">Interview Style</label>
                    <select
                      value={interviewStyle}
                      onChange={(e) => setInterviewStyle(e.target.value as any)}
                      className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white"
                    >
                      <option value="deep">Deep - Ask more probing follow-ups</option>
                      <option value="balanced">Balanced - Depth with time control</option>
                      <option value="fast">Fast - Fewer follow-ups, quicker pace</option>
                    </select>
                  </div>

                  <label className="flex items-center gap-3 p-3 bg-gray-800 rounded cursor-pointer">
                    <input
                      type="checkbox"
                      checked={includeConsent}
                      onChange={(e) => setIncludeConsent(e.target.checked)}
                    />
                    <div>
                      <div className="font-semibold text-sm">Include Consent Form</div>
                      <div className="text-xs text-gray-400">Respondents must agree before starting.</div>
                    </div>
                  </label>

                  {includeConsent && consentForm && (
                    <Card>
                      <div className="p-6">
                        <h3 className="font-semibold mb-3 flex items-center gap-2">
                          <span>📄</span> Consent Form Preview
                        </h3>
                        <div className="max-h-64 overflow-y-auto rounded-lg border border-white/10 bg-gray-900/60 p-4 text-sm text-gray-300 whitespace-pre-wrap">
                          {consentForm}
                        </div>
                      </div>
                    </Card>
                  )}
                </div>
              </div>
            </Card>

            {/* Conversation */}
            <Card>
              <div className="p-6">
                <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
                  <MessageCircle className="w-5 h-5 text-purple-500" />
                  Research Goal
                </h3>

                <div className="space-y-3 mb-4 max-h-64 overflow-y-auto">
                  {intakeConversation.length === 0 && (
                    <div className="p-4 bg-gray-800 rounded text-sm">
                      <p className="font-semibold mb-1">👋 Hi! I'm your AI research assistant.</p>
                      <p className="text-gray-300">Tell me what you want to learn from your respondents.</p>
                    </div>
                  )}
                  
                  {intakeConversation.map((msg, idx) => (
                    <div key={idx} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
                      {msg.role === 'ai' && (
                        <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center text-xs flex-shrink-0">🤖</div>
                      )}
                      <div
                        className={`p-3 rounded-lg max-w-xs ${
                          msg.role === 'user'
                            ? 'bg-cyan-600 text-white'
                            : 'bg-gray-700 text-gray-100'
                        }`}
                      >
                        {msg.message}
                      </div>
                    </div>
                  ))}
                  {isLoadingAI && (
                    <div className="flex gap-3">
                      <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center flex-shrink-0">🤖</div>
                      <div className="p-3 bg-gray-700 rounded-lg flex gap-1">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                      </div>
                    </div>
                  )}
                  <div ref={conversationEndRef} />
                </div>

                <div className="space-y-2">
                  <textarea
                    ref={goalInputRef}
                    placeholder="Describe what you want to learn..."
                    value={goalText}
                    onChange={(e) => setGoalText(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.ctrlKey && e.key === 'Enter') handleAnalyzeGoal();
                    }}
                    rows={3}
                    className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded text-white resize-none"
                  />
                  <Button
                    onClick={handleAnalyzeGoal}
                    disabled={isLoadingAI || !goalText.trim()}
                    className="w-full"
                  >
                    {isLoadingAI ? <Loader className="w-4 h-4 animate-spin" /> : '➤'} Send
                  </Button>
                </div>
              </div>
            </Card>
          </div>
        );

      case 1: // Review
        return (
          <div className="space-y-6">
            <Card>
              <div className="p-6 bg-gradient-to-r from-yellow-600 to-yellow-700">
                <h3 className="text-white font-semibold mb-2">📊 AI Analysis</h3>
              </div>
              <div className="p-6 space-y-3">
                <div>
                  <strong className="text-sm">Goal Summary:</strong>
                  <p className="text-sm text-gray-300 mt-1">{analyzedGoal}</p>
                </div>
                <div>
                  <strong className="text-sm">Interview Type:</strong>
                  <p className="text-sm text-gray-300 mt-1 capitalize">{interviewStyle}</p>
                </div>
              </div>
            </Card>

            <div>
              <h3 className="text-lg font-semibold mb-4">Generated Questions & Follow-ups</h3>
              <p className="text-sm text-gray-400 mb-4">Review the questions below. Each has follow-up questions.</p>
              
              <div className="space-y-3">
                {questions.map((q, idx) => (
                  <Card key={idx}>
                    <div className="p-4">
                      <div className="flex gap-2 mb-2">
                        <span className="text-xs bg-blue-600 px-2 py-1 rounded">Q{idx + 1}</span>
                        <span className={`text-xs px-2 py-1 rounded ${
                          q.depth === 1 ? 'bg-green-600' :
                          q.depth === 2 ? 'bg-yellow-600' :
                          'bg-red-600'
                        }`}>
                          {q.depth === 1 ? 'Icebreaker' : q.depth === 2 ? 'Core' : 'Deep'}
                        </span>
                      </div>
                      <p className="font-semibold mb-2">{q.question_text}</p>
                      {q.follow_ups && q.follow_ups.length > 0 && (
                        <div className="text-xs text-gray-400 ml-4 space-y-1">
                          <p className="font-semibold">Follow-ups:</p>
                          {q.follow_ups.map((fu, fidx) => (
                            <p key={fidx}>• {fu}</p>
                          ))}
                        </div>
                      )}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          </div>
        );

      case 2: // Briefing
        return (
          <div className="space-y-6">
            <Card className="border-l-4 border-l-cyan-500">
              <div className="p-6">
                <h3 className="text-lg font-semibold mb-2">ℹ️ Interview Briefing</h3>
                <p className="text-sm text-gray-300 mb-4">Here's what your respondents will experience:</p>
                <div className="space-y-2 text-sm text-gray-300">
                  <p>✓ Survey title: <strong>{surveyTitle}</strong></p>
                  <p>✓ Estimated duration: <strong>{interviewDuration} minutes</strong></p>
                  <p>✓ Total questions: <strong>{questions.length}</strong> with follow-ups</p>
                  <p>✓ Interview style: <strong className="capitalize">{interviewStyle}</strong></p>
                </div>
              </div>
            </Card>

            <Card>
              <div className="p-6">
                <h3 className="font-semibold mb-4">✅ After the Interview</h3>
                <ul className="space-y-2 text-sm">
                  <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" /> Complete transcript of all answers</li>
                  <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" /> Sentiment analysis per question</li>
                  <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" /> Key pain points identified</li>
                  <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" /> Executive summary report</li>
                  <li className="flex gap-2"><Check className="w-4 h-4 text-green-500 flex-shrink-0 mt-0.5" /> Actionable recommendations</li>
                </ul>
              </div>
            </Card>
          </div>
        );

      case 3: // Launch
        return (
          <div className="text-center space-y-6 py-6">
            <div className="text-5xl">🚀</div>
            <div>
              <h2 className="text-2xl font-bold mb-2">Your Survey is Ready!</h2>
              <p className="text-gray-400">Choose how you'd like to collect responses:</p>
            </div>

            <div className="grid grid-cols-3 gap-4">
              {[
                { id: 'web-form', icon: '📋', name: 'Web Form', desc: 'Progressive survey' },
                { id: 'chat', icon: '💬', name: 'Chat Interview', desc: 'WhatsApp-style conversation' },
                { id: 'voice', icon: '🎤', name: 'Voice Input', desc: 'Speak naturally' },
              ].map((channel) => (
                <Card
                  key={channel.id}
                  onClick={() => handleLaunch(channel.id)}
                  className="cursor-pointer hover:border-cyan-500 transition text-center p-4"
                >
                  <div className="text-3xl mb-2">{channel.icon}</div>
                  <h3 className="font-semibold">{channel.name}</h3>
                  <p className="text-xs text-gray-400 mt-1">{channel.desc}</p>
                </Card>
              ))}
            </div>
          </div>
        );

      default:
        return null;
    }
  };

  return (
    <div className="max-w-4xl mx-auto py-8 px-4">
      {/* Step Indicators */}
      <div className="flex gap-2 mb-8">
        {steps.map((step, idx) => (
          <div key={idx} className="flex items-center">
            <div
              className={`w-10 h-10 rounded-full flex items-center justify-center font-semibold ${
                idx === currentStep
                  ? 'bg-cyan-600 text-white'
                  : idx < currentStep
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-700 text-gray-400'
              }`}
            >
              {idx < currentStep ? '✓' : idx + 1}
            </div>
            <div className="text-sm font-semibold ml-2">{step}</div>
            {idx < steps.length - 1 && <ChevronRight className="w-4 h-4 mx-2 text-gray-600" />}
          </div>
        ))}
      </div>

      {/* Content */}
      {renderStepContent()}

      {/* Navigation */}
      <div className="flex justify-between mt-8">
        <Button
          variant="secondary"
          onClick={() => setCurrentStep(Math.max(0, currentStep - 1))}
          disabled={currentStep === 0}
        >
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>

        <Button
          onClick={() => setCurrentStep(Math.min(steps.length - 1, currentStep + 1))}
          disabled={currentStep === steps.length - 1 || !deepResult || isPublishing}
        >
          {isPublishing ? <Loader className="w-4 h-4 animate-spin" /> : <>Next <ChevronRight className="w-4 h-4" /></>}
        </Button>
      </div>
    </div>
  );
}
