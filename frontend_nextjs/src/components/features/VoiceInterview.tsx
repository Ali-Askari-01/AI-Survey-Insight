'use client';

import { useState, useRef, useEffect } from 'react';
import { Card } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { clientApi } from '@/lib/clientApi';
import { Loader, Mic, MicOff, SkipForward, Volume2 } from 'lucide-react';

interface VoiceResponse {
  question_id: string;
  transcript: string;
  audio_url?: string;
  sentiment?: string;
  timestamp: string;
}

export default function VoiceInterview() {
  const [surveyId, setSurveyId] = useState<string | null>(null);
  const [questions, setQuestions] = useState<any[]>([]);
  const [currentQuestionIdx, setCurrentQuestionIdx] = useState(0);
  const [isRecording, setIsRecording] = useState(false);
  const [mediaRecorder, setMediaRecorder] = useState<MediaRecorder | null>(null);
  const [liveTranscript, setLiveTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [responses, setResponses] = useState<VoiceResponse[]>([]);
  const [progress, setProgress] = useState(0);

  const mediaStreamRef = useRef<MediaStream | null>(null);
  const audioChunksRef = useRef<Blob[]>([]);
  const recognitionRef = useRef<any>(null);

  useEffect(() => {
    loadSurvey();
    initializeSpeechRecognition();
  }, []);

  const loadSurvey = async () => {
    try {
      const surveys = await clientApi.surveys.list();
      if (surveys && surveys.length > 0) {
        setSurveyId(surveys[0].id);
        const qs = await clientApi.surveys.getQuestions(surveys[0].id);
        setQuestions(qs);
        setProgress((0 / qs.length) * 100);
      }
    } catch (error) {
      console.error('Failed to load survey:', error);
      alert('Could not load survey. Please try again.');
    }
  };

  const initializeSpeechRecognition = () => {
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert('Speech Recognition not supported in your browser');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onresult = (event: any) => {
      let interim = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcript = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          setFinalTranscript((prev) => prev + ' ' + transcript);
        } else {
          interim += transcript;
        }
      }
      setLiveTranscript(interim);
    };

    recognition.onerror = (event: any) => {
      console.error('Speech recognition error:', event.error);
    };

    recognitionRef.current = recognition;
  };

  const startRecording = async () => {
    try {
      audioChunksRef.current = [];
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;

      const recorder = new MediaRecorder(stream);
      recorder.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      recorder.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: 'audio/webm' });
        await uploadAndTranscribe(audioBlob);
      };

      recorder.start();
      setMediaRecorder(recorder);
      setIsRecording(true);
      setFinalTranscript('');
      setLiveTranscript('');

      // Start speech recognition for live preview
      recognitionRef.current?.start();
    } catch (error) {
      console.error('Failed to start recording:', error);
      alert('Could not access microphone.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      setIsRecording(false);
      recognitionRef.current?.stop();

      // Stop all audio tracks
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop());
    }
  };

  const uploadAndTranscribe = async (audioBlob: Blob) => {
    setIsLoading(true);
    try {
      const currentQuestion = questions[currentQuestionIdx];
      if (!currentQuestion) return;

      // Upload audio to backend (backend will use AssemblyAI)
      const formData = new FormData();
      formData.append('audio', audioBlob);
      formData.append('survey_id', surveyId!);
      formData.append('question_id', currentQuestion.id);

      const result = await fetch('/api/transcribe', {
        method: 'POST',
        body: formData,
      });

      if (!result.ok) throw new Error('Transcription failed');

      const data = await result.json();
      const transcript = data.transcript || finalTranscript;

      // Save response
      const response: VoiceResponse = {
        question_id: currentQuestion.id,
        transcript,
        audio_url: data.audio_url,
        sentiment: data.sentiment,
        timestamp: new Date().toISOString(),
      };

      setResponses([...responses, response]);
      setFinalTranscript('');

      // Move to next question
      if (currentQuestionIdx < questions.length - 1) {
        setCurrentQuestionIdx(currentQuestionIdx + 1);
        setProgress(((currentQuestionIdx + 1) / questions.length) * 100);
      } else {
        // Survey complete
        alert('Survey complete! Thank you for your responses.');
        await submitResponses([...responses, response]);
      }
    } catch (error) {
      console.error('Transcription error:', error);
      alert('Transcription failed. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const submitResponses = async (allResponses: VoiceResponse[]) => {
    try {
      await clientApi.surveys.submitResponses(surveyId!, {
        responses: allResponses,
        channel: 'voice',
      });
      // Redirect to results or thank you page
    } catch (error) {
      console.error('Failed to submit responses:', error);
    }
  };

  const skipQuestion = () => {
    if (currentQuestionIdx < questions.length - 1) {
      setCurrentQuestionIdx(currentQuestionIdx + 1);
      setProgress(((currentQuestionIdx + 1) / questions.length) * 100);
      setFinalTranscript('');
      setLiveTranscript('');
    }
  };

  if (!surveyId || questions.length === 0) {
    return (
      <div className="flex items-center justify-center h-screen">
        <Card className="p-8 text-center">
          <Loader className="w-8 h-8 animate-spin mx-auto mb-4" />
          <p>Loading survey...</p>
        </Card>
      </div>
    );
  }

  const currentQuestion = questions[currentQuestionIdx];
  const isComplete = currentQuestionIdx >= questions.length;

  return (
    <div className="min-h-screen flex flex-col bg-black">
      {/* Header */}
      <div className="p-6 border-b border-gray-800">
        <div className="max-w-2xl mx-auto">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold">Voice Interview</h1>
              <p className="text-gray-400 text-sm">Question {currentQuestionIdx + 1} of {questions.length}</p>
            </div>
            <Volume2 className="w-6 h-6 text-cyan-500" />
          </div>
          {/* Progress bar */}
          <div className="w-full bg-gray-800 rounded-full h-2">
            <div
              className="bg-gradient-to-r from-cyan-500 to-purple-600 h-2 rounded-full transition-all"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex items-center justify-center p-6">
        <div className="max-w-2xl w-full space-y-6">
          {/* Question Card */}
          {!isComplete && (
            <>
              <Card className="p-8 text-center">
                <div className="mb-6 text-4xl opacity-60">🤖</div>
                <h2 className="text-2xl font-semibold mb-4">{currentQuestion.question_text}</h2>
                <p className="text-gray-400">Speak your response naturally. We'll transcribe and analyze it.</p>
              </Card>

              {/* Visualization */}
              {isRecording && (
                <Card className="p-6">
                  <div className="flex justify-center gap-2 mb-6">
                    {[...Array(20)].map((_, i) => (
                      <div
                        key={i}
                        className="w-1 bg-cyan-500 rounded-full"
                        style={{
                          height: `${Math.random() * 60 + 20}px`,
                          animation: 'pulse 0.4s ease-in-out infinite',
                          animationDelay: `${i * 0.05}s`,
                        }}
                      />
                    ))}
                  </div>
                  <p className="text-center text-sm text-gray-400">Recording...</p>
                </Card>
              )}

              {/* Transcript Preview */}
              {liveTranscript && (
                <Card className="p-4 bg-gray-900">
                  <p className="text-xs text-gray-500 mb-2">Live Preview:</p>
                  <p className="text-sm text-gray-200 italic">{liveTranscript}</p>
                </Card>
              )}

              {/* Final Transcript */}
              {finalTranscript && (
                <Card className="p-4 bg-gray-900">
                  <p className="text-xs text-green-500 mb-2">✓ Transcribed:</p>
                  <p className="text-sm text-gray-100">{finalTranscript}</p>
                </Card>
              )}

              {/* Controls */}
              <div className="flex gap-4">
                {!isRecording ? (
                  <Button
                    onClick={startRecording}
                    disabled={isLoading}
                    className="flex-1 flex items-center justify-center gap-2"
                  >
                    <Mic className="w-5 h-5" />
                    Start Recording
                  </Button>
                ) : (
                  <Button
                    onClick={stopRecording}
                    variant="secondary"
                    className="flex-1 flex items-center justify-center gap-2"
                  >
                    <MicOff className="w-5 h-5" />
                    Stop Recording
                  </Button>
                )}
                <Button
                  onClick={skipQuestion}
                  variant="secondary"
                  disabled={isRecording}
                  className="flex items-center justify-center gap-2"
                >
                  <SkipForward className="w-5 h-5" />
                  Skip
                </Button>
              </div>
            </>
          )}

          {/* Complete Screen */}
          {isComplete && (
            <Card className="p-8 text-center">
              <div className="text-5xl mb-4">✅</div>
              <h2 className="text-2xl font-bold mb-2">Survey Complete!</h2>
              <p className="text-gray-400 mb-6">Thank you for your responses. We're analyzing your interview now.</p>
              <Button
                onClick={() => (window.location.href = '/app/insights')}
                className="mx-auto"
              >
                View Results
              </Button>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
