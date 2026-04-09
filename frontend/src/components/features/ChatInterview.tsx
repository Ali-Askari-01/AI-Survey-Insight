'use client';

import { useState, useRef, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { clientApi } from '@/lib/clientApi';
import { Send, Loader } from 'lucide-react';

interface Message {
  id: string;
  role: 'user' | 'ai';
  content: string;
  timestamp: string;
  quickReplies?: string[];
}

export default function ChatInterview() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const [currentQuestion, setCurrentQuestion] = useState(0);
  const [totalQuestions, setTotalQuestions] = useState(0);
  const [sessionId, setSessionId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    initializeChat();
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const initializeChat = async () => {
    try {
      setIsLoading(true);
      const surveys = await clientApi.surveys.list();
      if (surveys && surveys.length > 0) {
        const survey = surveys[0];

        const questions = await clientApi.surveys.getQuestions(survey.id);
        setTotalQuestions(questions.length);

        // Start chat session
        const session = await clientApi.surveys.startChatSession(survey.id);
        setSessionId(session.id);

        // Get initial AI greeting
        const initialMsg = await clientApi.surveys.getChatMessage(session.id);
        const aiMsg: Message = {
          id: `msg-${Date.now()}`,
          role: 'ai',
          content: initialMsg.message || `Hello! I'm your AI interviewer. Let's explore your thoughts. I have ${questions.length} questions for you, and this should take about 15 minutes.`,
          timestamp: new Date().toISOString(),
          quickReplies: initialMsg.quick_replies || [],
        };
        setMessages([aiMsg]);
        setCurrentQuestion(0);
      }
    } catch (error) {
      console.error('Failed to initialize chat:', error);
      alert('Could not start chat interview.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSendMessage = async (text?: string) => {
    const messageText = text || inputValue.trim();
    if (!messageText || !sessionId || isLoading) return;

    // Add user message
    const userMsg: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: messageText,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');

    setIsLoading(true);
    setIsTyping(true);

    try {
      // Send to backend
      const response = await clientApi.surveys.sendChatMessage(sessionId, {
        message: messageText,
        question_index: currentQuestion,
      });

      // Add AI response with simulated typing delay
      setTimeout(() => {
        const aiMsg: Message = {
          id: `msg-${Date.now() + 1}`,
          role: 'ai',
          content: response.message || 'Thank you for that response.',
          timestamp: new Date().toISOString(),
          quickReplies: response.quick_replies || [],
        };
        setMessages((prev) => [...prev, aiMsg]);
        setIsTyping(false);

        if (response.question_index !== undefined) {
          setCurrentQuestion(response.question_index);
        }

        if (response.is_complete) {
          setTimeout(() => {
            const completeMsg: Message = {
              id: `msg-${Date.now() + 2}`,
              role: 'ai',
              content: "Thank you for completing the interview! I'm analyzing your responses now.",
              timestamp: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, completeMsg]);
          }, 500);
        }

        inputRef.current?.focus();
      }, 800);
    } catch (error) {
      console.error('Failed to send message:', error);
      setIsTyping(false);
      const errorMsg: Message = {
        id: `msg-${Date.now() + 1}`,
        role: 'ai',
        content: "Sorry, I didn't catch that. Could you please repeat?",
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const lastMessage = messages[messages.length - 1];
  const quickReplies = lastMessage?.quickReplies || [];
  const progress = totalQuestions > 0 ? ((currentQuestion + 1) / totalQuestions) * 100 : 0;

  return (
    <div className="h-screen flex flex-col bg-black">
      {/* Header */}
      <div className="border-b border-gray-800 p-4 bg-gradient-to-r from-gray-900 to-black">
        <div className="max-w-4xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-purple-600 flex items-center justify-center text-lg">🤖</div>
              <div>
                <h1 className="font-semibold">AI Interviewer</h1>
                <p className="text-xs text-gray-400">{isTyping ? 'typing...' : 'online'}</p>
              </div>
            </div>
            {totalQuestions > 0 && (
              <div className="text-right">
                <p className="text-sm text-gray-400">
                  Question <span className="font-semibold text-cyan-400">{currentQuestion + 1}</span> of {totalQuestions}
                </p>
              </div>
            )}
          </div>
          {/* Progress bar */}
          <div className="w-full bg-gray-800 rounded-full h-1">
            <div
              className="bg-gradient-to-r from-cyan-500 to-purple-600 h-1 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <div className="max-w-2xl mx-auto w-full space-y-4">
          {isLoading && messages.length === 0 ? (
            <div className="flex items-center justify-center h-64">
              <Loader className="w-8 h-8 animate-spin text-cyan-500" />
            </div>
          ) : (
            <>
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'ai' && (
                    <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center text-xs flex-shrink-0 mr-3 mt-1">
                      🤖
                    </div>
                  )}
                  <div
                    className={`max-w-xs rounded-lg p-4 ${
                      msg.role === 'user'
                        ? 'bg-cyan-600 text-white'
                        : 'bg-gray-800 text-gray-100'
                    }`}
                  >
                    <p className="text-sm">{msg.content}</p>
                  </div>
                </div>
              ))}

              {isTyping && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center text-xs flex-shrink-0">
                    🤖
                  </div>
                  <div className="bg-gray-800 rounded-lg p-4 flex gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </>
          )}
        </div>
      </div>

      {/* Quick Replies & Input */}
      <div className="border-t border-gray-800 p-4 bg-gradient-to-t from-black to-gray-900">
        <div className="max-w-2xl mx-auto space-y-3">
          {/* Quick Reply Buttons */}
          {quickReplies.length > 0 && (
            <div className="flex gap-2 flex-wrap">
              {quickReplies.map((reply, idx) => (
                <Button
                  key={idx}
                  variant="secondary"
                  size="sm"
                  onClick={() => handleSendMessage(reply)}
                  className="text-xs"
                  disabled={isLoading}
                >
                  {reply}
                </Button>
              ))}
            </div>
          )}

          {/* Text Input */}
          <div className="flex gap-2">
            <Input
              ref={inputRef}
              placeholder="Type your response..."
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSendMessage();
                }
              }}
              disabled={isLoading}
              className="flex-1"
            />
            <Button
              onClick={() => handleSendMessage()}
              disabled={isLoading || !inputValue.trim()}
              className="flex items-center justify-center gap-2"
            >
              {isLoading ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
