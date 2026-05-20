import { useCallback, useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { Upload, MessageSquare, Gavel, CheckCircle, Trash2, AlertTriangle, RefreshCw } from 'lucide-react';

const API_BASE = "https://9pgo3cfzsk.execute-api.us-east-1.amazonaws.com/Prod";

/**
 * Human-readable breakdown of axios/API failures (502/RDS, CORS-masked network errors, etc.).
 * @param {boolean} forCasesList - true for GET /cases errors; false for chat and other calls.
 * @returns {{ headline: string, hints: string[], httpStatus?: number }}
 */
function describeApiFailure(err, forCasesList = true) {
  if (axios.isAxiosError(err)) {
    const res = err.response;
    const status = res?.status;
    const statusText = res?.statusText;
    const data = res?.data;
    let bodyText = '';
    if (typeof data === 'string') bodyText = data.trim();
    else if (data && typeof data === 'object') {
      bodyText = String(data.message ?? data.error ?? '').trim();
    }

    const noResponse = !res && (err.code === 'ERR_NETWORK' || err.message === 'Network Error');
    if (noResponse) {
      return {
        headline: forCasesList
          ? 'Could not load the case list (network error)'
          : 'Could not reach the chat API (network error)',
        hints: [
          'The browser did not get a normal HTTP response. This often happens when API Gateway returns 502/503 while Lambda or a dependency (for example RDS) is down—those error pages sometimes omit CORS headers, so DevTools shows a CORS or network error instead of the real status.',
          forCasesList
            ? 'Case Intelligence below uses the Knowledge Base route and may still work when that function is healthy.'
            : 'Verify the POST /chat Lambda and Bedrock Knowledge Base configuration if problems persist.',
        ],
        httpStatus: undefined,
      };
    }

    const hints = [];
    if (status) {
      hints.push(
        `HTTP ${status}${statusText && statusText !== 'unknown' ? ` ${statusText}` : ''}${bodyText ? ` — ${bodyText}` : ''}`.trim()
      );
    } else if (bodyText) {
      hints.push(bodyText);
    }

    let headline = forCasesList ? 'Cases API request failed' : 'Chat request failed';
    if (status === 502 || status === 503) {
      headline = forCasesList ? 'Case list unavailable (bad gateway)' : 'Chat service unavailable (bad gateway)';
      hints.push(
        forCasesList
          ? 'Usually the Lambda behind GET /cases could not talk to RDS or another dependency. Restore the database or check CloudWatch logs. Case Intelligence may still work via the Knowledge Base.'
          : 'The chat Lambda or Bedrock agent may be failing. Check CloudWatch and IAM permissions for retrieve_and_generate.'
      );
    } else if (status === 500) {
      headline = forCasesList ? 'Cases API internal error' : 'Chat API internal error';
      hints.push(
        forCasesList
          ? 'Check Lambda logs for the list-cases handler. Chat uses a separate endpoint.'
          : 'Check Lambda logs for the chat handler and Bedrock responses.'
      );
    } else if (status === 403 || status === 401) {
      headline = forCasesList ? 'Cases API rejected the request' : 'Chat API rejected the request';
    }

    if (!hints.length) hints.push(err.message || 'Unknown error');

    return { headline, hints, httpStatus: status };
  }

  return {
    headline: 'Request failed',
    hints: [String(err?.message || err || 'Unknown error')],
    httpStatus: undefined,
  };
}

function formatFailureForChat(err) {
  const { headline, hints } = describeApiFailure(err, false);
  return [headline, ...hints].join('\n');
}

function App() {
  const fileInputRef = useRef(null);
  const caseRefreshTimerRef = useRef(null);
  const [cases, setCases] = useState([]);
  const [casesFetchError, setCasesFetchError] = useState(null);
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [isUploading, setIsUploading] = useState(false);
  const [isProcessingUpload, setIsProcessingUpload] = useState(false);
  const [isChatting, setIsChatting] = useState(false);
  const [deletingCaseId, setDeletingCaseId] = useState(null);

  const fetchCases = useCallback(async () => {
    try {
      const res = await axios.get(`${API_BASE}/cases`);
      const data = Array.isArray(res.data) ? res.data : [];
      setCases(data);
      setCasesFetchError(null);
      return data;
    } catch (err) {
      console.error('API Error', err);
      setCasesFetchError(describeApiFailure(err, true));
      return null;
    }
  }, []);

  useEffect(() => { fetchCases(); }, [fetchCases]);

  useEffect(() => {
    return () => {
      if (caseRefreshTimerRef.current) {
        clearTimeout(caseRefreshTimerRef.current);
      }
    };
  }, []);

  const startCaseRefreshPolling = (previousCaseCount) => {
    if (caseRefreshTimerRef.current) {
      clearTimeout(caseRefreshTimerRef.current);
    }

    setIsProcessingUpload(true);
    let attempts = 0;
    const maxAttempts = 24;

    const poll = async () => {
      attempts += 1;
      const latestCases = await fetchCases();
      if (latestCases === null) {
        if (attempts >= maxAttempts) {
          setIsProcessingUpload(false);
          caseRefreshTimerRef.current = null;
          return;
        }
        caseRefreshTimerRef.current = setTimeout(poll, 5000);
        return;
      }

      const hasNewCase = latestCases.length > previousCaseCount;

      if (hasNewCase || attempts >= maxAttempts) {
        setIsProcessingUpload(false);
        caseRefreshTimerRef.current = null;
        return;
      }

      caseRefreshTimerRef.current = setTimeout(poll, 5000);
    };

    caseRefreshTimerRef.current = setTimeout(poll, 5000);
  };

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || isUploading) return;

    setIsUploading(true);
    try {
      const previousCaseCount = cases.length;
      const contentType = file.type || "audio/mpeg";
      const signRes = await axios.get(`${API_BASE}/sign`, {
        params: {
          file_name: file.name,
          file_type: contentType,
        },
      });
      const uploadUrl = signRes.data?.upload_url;

      if (!uploadUrl) {
        throw new Error("Upload URL was not returned by the API");
      }

      await axios.put(uploadUrl, file, {
        headers: { "Content-Type": contentType },
      });
      startCaseRefreshPolling(previousCaseCount);
    } catch (err) {
      console.error('Upload Failed', err);
      alert("Upload Failed");
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleChat = async () => {
    const trimmedQuestion = question.trim();
    if (!trimmedQuestion || isChatting) return;

    setIsChatting(true);
    setQuestion("");
    setMessages((prev) => [...prev, { role: "user", text: trimmedQuestion }]);

    try {
      const res = await axios.post(`${API_BASE}/chat`, { question: trimmedQuestion });
      setMessages((prev) => [...prev, { role: "assistant", text: res.data.answer }]);
    } catch (err) {
      console.error("Chat failed", err);
      const fromBody = err.response?.data?.error || err.response?.data?.message;
      const message = fromBody
        ? `Error: ${fromBody}`
        : `Error:\n${formatFailureForChat(err)}`;
      setMessages((prev) => [...prev, { role: "assistant", text: message }]);
    }
    setIsChatting(false);
  };

  const handleChatKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleChat();
    }
  };

  const handleDeleteCase = async (caseItem) => {
    if (!caseItem.id || deletingCaseId) return;

    const confirmed = window.confirm(`Delete ${caseItem.client || "this client"} and related files?`);
    if (!confirmed) return;

    setDeletingCaseId(caseItem.id);
    try {
      await axios.delete(`${API_BASE}/cases/${caseItem.id}`);
      await fetchCases();
    } catch (err) {
      console.error("Delete failed", err);
      const message = err.response?.data?.error || err.message || "Delete failed";
      alert(message);
    } finally {
      setDeletingCaseId(null);
    }
  };

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 p-8 font-sans">
      <header className="flex items-center gap-3 mb-10 pb-6 border-b border-gray-800">
        <Gavel size={32} className="text-blue-500" />
        <h1 className="text-2xl font-bold">LexiGuard <span className="text-blue-500 text-lg uppercase tracking-widest ml-1">Intelligence</span></h1>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
        <div className="lg:col-span-8 space-y-8">
          <div className="bg-gray-900 p-6 rounded-2xl border border-gray-800 shadow-xl">
            <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 text-blue-400"><Upload size={18} /> New Case Intake</h2>
            <p className="text-sm text-gray-400 mb-4 leading-relaxed">
              Upload a <span className="text-gray-300">legal-audio</span> recording for a new matter. Allowed files are standard browser audio types (for example <span className="font-mono text-gray-300">.mp3</span>, <span className="font-mono text-gray-300">.m4a</span>, <span className="font-mono text-gray-300">.wav</span>, <span className="font-mono text-gray-300">.webm</span>)—anything your file picker offers under audio. After processing, the case appears in the table below.
            </p>
            <input
              ref={fileInputRef}
              type="file"
              accept="audio/*"
              onChange={handleUpload}
              disabled={isUploading}
              className="block text-sm text-gray-400 file:mr-4 file:py-2 file:px-6 file:rounded-lg file:border-0 file:text-sm file:font-semibold file:bg-blue-600 file:text-white hover:file:bg-blue-700 disabled:opacity-60 disabled:cursor-not-allowed cursor-pointer"
            />
            {isUploading && <div className="mt-4 text-blue-400 animate-pulse">Uploading to S3...</div>}
            {isProcessingUpload && !isUploading && <div className="mt-4 text-blue-400 animate-pulse">Processing audio and refreshing cases...</div>}
          </div>

          <div className="bg-gray-900 rounded-2xl border border-gray-800 shadow-xl overflow-hidden">
            {casesFetchError && (
              <div className="border-b border-amber-500/30 bg-amber-950/25 p-4 text-sm">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="flex min-w-0 flex-1 gap-3">
                    <AlertTriangle className="mt-0.5 h-5 w-5 shrink-0 text-amber-400" aria-hidden />
                    <div className="min-w-0">
                      <p className="font-medium text-amber-100">{casesFetchError.headline}</p>
                      <ul className="mt-2 list-disc space-y-1.5 pl-5 text-xs leading-relaxed text-amber-100/85">
                        {casesFetchError.hints.map((line, i) => (
                          <li key={i}>{line}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                  <button
                    type="button"
                    onClick={() => void fetchCases()}
                    className="inline-flex shrink-0 items-center justify-center gap-2 self-start rounded-lg border border-amber-500/40 bg-amber-900/40 px-3 py-2 text-xs font-medium text-amber-100 hover:bg-amber-900/60"
                  >
                    <RefreshCw size={14} aria-hidden />
                    Retry cases
                  </button>
                </div>
              </div>
            )}
            <table className="w-full text-left">
              <thead className="text-gray-500 text-xs uppercase bg-gray-800/50">
                <tr><th className="p-4">Client</th><th className="p-4">Matter</th><th className="p-4 text-right">Fee</th><th className="p-4 text-center">Status</th><th className="p-4 text-right">Action</th></tr>
              </thead>
              <tbody className="text-sm">
                {cases.map((item, idx) => (
                  <tr key={item.id ?? idx} className="border-t border-gray-800 hover:bg-gray-800/30">
                    <td className="p-4 font-medium">{item.client}</td>
                    <td className="p-4 text-gray-400">{item.type}</td>
                    <td className="p-4 text-right text-green-400 font-mono">{item.fee}</td>
                    <td className="p-4 text-center text-blue-400"><CheckCircle size={16} className="mx-auto" /></td>
                    <td className="p-4 text-right">
                      <button
                        type="button"
                        onClick={() => handleDeleteCase(item)}
                        disabled={!item.id || deletingCaseId === item.id}
                        title="Delete case"
                        className="inline-flex h-9 w-9 items-center justify-center rounded-lg text-gray-500 hover:bg-red-500/10 hover:text-red-400 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  </tr>
                ))}
                {cases.length === 0 && !casesFetchError && (
                  <tr>
                    <td colSpan={5} className="p-6 text-center text-gray-500 text-sm">
                      No cases loaded yet. Upload legal audio above, or wait for processing.
                    </td>
                  </tr>
                )}
                {cases.length === 0 && casesFetchError && (
                  <tr>
                    <td colSpan={5} className="p-4 text-center text-gray-500 text-xs">
                      Table hidden until the cases API succeeds — use Retry above.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        <div className="lg:col-span-4 bg-gray-900 p-6 rounded-2xl border border-gray-800 shadow-xl flex flex-col h-[600px]">
          <h2 className="text-lg font-semibold mb-3 flex items-center gap-2 border-b border-gray-800 pb-4 text-purple-400"><MessageSquare size={18} /> Case Intelligence</h2>
          <p className="text-xs text-gray-500 mb-4 leading-relaxed">
            Ask natural-language questions about your uploaded legal audio and extracted case knowledge (clients, matters, fees, timelines, disputes). Use <span className="text-gray-400">Enter</span> to send; answers draw from the knowledge base built from your intakes.
            {casesFetchError && (
              <span className="mt-2 block rounded-lg border border-purple-500/25 bg-purple-950/20 p-2 text-purple-200/90">
                The case list uses the database; if it fails, you can still try Case Intelligence—answers come from the Knowledge Base, not the cases table.
              </span>
            )}
          </p>
          <div className="flex-grow overflow-y-auto mb-6 text-sm text-gray-300 bg-black/20 p-4 rounded-xl space-y-4">
            {messages.length === 0 && !isChatting && (
              <div className="text-gray-500 space-y-2">
                <p className="text-sm">Start by typing a question below—for example, summarize a party&apos;s position, list key dates, or clarify fee terms.</p>
                <p className="text-xs text-gray-600">Upload at least one legal-audio intake first so the model has case context to work from.</p>
              </div>
            )}
            {messages.map((message, idx) => (
              <div
                key={idx}
                className={`flex ${message.role === "user" ? "justify-end" : "justify-start"}`}
              >
                <div
                  className={`max-w-[85%] rounded-2xl px-4 py-3 leading-relaxed ${
                    message.role === "user"
                      ? "bg-blue-600 text-white rounded-br-md"
                      : "bg-gray-800 text-gray-100 rounded-bl-md border border-gray-700 whitespace-pre-wrap break-words"
                  }`}
                >
                  {message.text}
                </div>
              </div>
            ))}
            {isChatting && (
              <div className="flex justify-start">
                <div className="bg-gray-800 text-gray-400 border border-gray-700 rounded-2xl rounded-bl-md px-4 py-3 animate-pulse">
                  AI is thinking...
                </div>
              </div>
            )}
          </div>
          <div className="flex gap-2 bg-gray-800 p-2 rounded-xl border border-gray-700">
            <input
              value={question}
              onChange={(e)=>setQuestion(e.target.value)}
              onKeyDown={handleChatKeyDown}
              disabled={isChatting}
              className="bg-transparent border-0 flex-grow p-2 text-sm outline-none disabled:text-gray-500"
              placeholder="Type your question..."
            />
            <button
              onClick={handleChat}
              disabled={isChatting || !question.trim()}
              className="bg-blue-600 px-4 py-2 rounded-lg hover:bg-blue-700 disabled:bg-gray-700 disabled:text-gray-400 disabled:cursor-not-allowed"
            >
              Ask
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
