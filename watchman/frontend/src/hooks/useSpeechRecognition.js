import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Custom React hook for Web Speech API SpeechRecognition
 * Supports multi-language: English ('en-IN', 'en-US'), Tamil ('ta-IN'), and Tanglish.
 */
export const useSpeechRecognition = () => {
  const [isSupported, setIsSupported] = useState(false);
  const [isListening, setIsListening] = useState(false);
  const [transcript, setTranscript] = useState('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [error, setError] = useState(null);
  
  const recognitionRef = useRef(null);

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (SpeechRecognition) {
      setIsSupported(true);
    } else {
      setIsSupported(false);
    }

    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.abort();
        } catch {
          // ignore cleanup abort error
        }
      }
    };
  }, []);

  const startListening = useCallback(({
    lang = 'ta-IN',
    continuous = false,
    onResult,
    onError,
    onEnd
  } = {}) => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      const err = 'Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.';
      setError(err);
      if (onError) onError(err);
      return;
    }

    setError(null);
    setTranscript('');
    setInterimTranscript('');

    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch {
        // ignore
      }
    }

    try {
      const recognition = new SpeechRecognition();
      recognitionRef.current = recognition;

      recognition.lang = lang;
      recognition.continuous = continuous;
      recognition.interimResults = true;
      recognition.maxAlternatives = 1;

      recognition.onstart = () => {
        setIsListening(true);
      };

      recognition.onresult = (event) => {
        let finalStr = '';
        let interimStr = '';

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const item = event.results[i];
          if (item.isFinal) {
            finalStr += item[0].transcript;
          } else {
            interimStr += item[0].transcript;
          }
        }

        if (finalStr) {
          setTranscript((prev) => (prev ? `${prev} ${finalStr}` : finalStr));
          if (onResult) {
            onResult(finalStr, true);
          }
        }

        setInterimTranscript(interimStr);
        if (interimStr && onResult) {
          onResult(interimStr, false);
        }
      };

      recognition.onerror = (event) => {
        let errMsg = event.error;
        if (event.error === 'not-allowed') {
          errMsg = 'Microphone access denied. Please allow microphone permissions in your browser.';
        } else if (event.error === 'no-speech') {
          errMsg = 'No speech detected. Please speak into the microphone.';
        } else if (event.error === 'network') {
          errMsg = 'Network issue with speech recognition service.';
        }
        setError(errMsg);
        setIsListening(false);
        if (onError) onError(errMsg);
      };

      recognition.onend = () => {
        setIsListening(false);
        if (onEnd) onEnd();
      };

      recognition.start();
    } catch (err) {
      console.error('Error starting speech recognition:', err);
      setError(err.message || 'Failed to start microphone');
      setIsListening(false);
      if (onError) onError(err.message);
    }
  }, []);

  const stopListening = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop();
      } catch {
        // ignore
      }
    }
    setIsListening(false);
  }, []);

  return {
    isSupported,
    isListening,
    transcript,
    interimTranscript,
    error,
    startListening,
    stopListening
  };
};
