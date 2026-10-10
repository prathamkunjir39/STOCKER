import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  Sparkles,
  X,
  Send,
  RotateCcw,
  Bot,
  User,
  ArrowRight,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { chatbotAPI, ChatbotResponse } from "@/services/api";
import { cn } from "@/lib/utils";

interface ChatMessage {
  id: string;
  sender: "user" | "bot";
  text: string;
  time: string;
  action?: {
    label: string;
    path: string;
  };
  suggestions?: string[];
}

const INITIAL_SUGGESTIONS = [
  "🚨 Which items have critical low stock?",
  "📈 What is the sales forecast for Brake Pads?",
  "💡 Explain how cluster analysis helps us",
  "🛒 How do I reorder inventory?",
  "📊 Give me today's operational summary",
];

export function ChatbotWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      sender: "bot",
      text: "👋 Hi! I am your **Stocker AI Copilot**.\n\nI can help you look up live stock levels, check demand forecasts, list urgent alerts, or explain any feature in simple words. How can I assist you today?",
      time: "Just now",
      suggestions: INITIAL_SUGGESTIONS,
    },
  ]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    if (isOpen) {
      scrollToBottom();
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen, messages]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = (textToSend ?? input).trim();
    if (!query || loading) return;

    const userMsg: ChatMessage = {
      id: `u-${Date.now()}`,
      sender: "user",
      text: query,
      time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMsg]);
    if (!textToSend) setInput("");
    setLoading(true);

    try {
      const res = await chatbotAPI.sendMessage(query);
      const data: ChatbotResponse = res.data;

      const botMsg: ChatMessage = {
        id: `b-${Date.now()}`,
        sender: "bot",
        text: data.reply,
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        action: data.action,
        suggestions: data.suggestions,
      };

      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      const errorMsg: ChatMessage = {
        id: `err-${Date.now()}`,
        sender: "bot",
        text: "⚠️ Sorry, I encountered an issue connecting to the database. Please try again or navigate using the side menu.",
        time: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
        suggestions: ["Check critical stock", "Show executive KPIs"],
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setMessages([
      {
        id: "welcome-reset",
        sender: "bot",
        text: "Chat cleared. What would you like to check in the system?",
        time: "Just now",
        suggestions: INITIAL_SUGGESTIONS,
      },
    ]);
  };

  // Helper to render bold markdown and linebreaks
  const renderFormattedText = (content: string) => {
    return content.split("\n").map((line, idx) => {
      // Bold replacer: **text** -> <strong>text</strong>
      const parts = line.split(/(\*\*.*?\*\*)/g);
      return (
        <span key={idx} className="block min-h-[1.2rem]">
          {parts.map((part, pIdx) => {
            if (part.startsWith("**") && part.endsWith("**")) {
              return (
                <strong key={pIdx} className="font-semibold text-[var(--text)]">
                  {part.slice(2, -2)}
                </strong>
              );
            }
            if (part.startsWith("*") && part.endsWith("*")) {
              return (
                <em key={pIdx} className="italic text-[var(--muted)]">
                  {part.slice(1, -1)}
                </em>
              );
            }
            return part;
          })}
        </span>
      );
    });
  };

  return (
    <>
      {/* Floating Trigger Button */}
      <div className="fixed bottom-6 right-6 z-50">
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          type="button"
          onClick={() => setIsOpen(!isOpen)}
          className={cn(
            "relative flex h-14 items-center gap-2.5 rounded-full px-4 text-white shadow-xl transition-all duration-300",
            isOpen
              ? "bg-slate-800 text-white hover:bg-slate-900 border border-slate-700"
              : "bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-blue-500/25"
          )}
          aria-label="Toggle AI Copilot"
        >
          {isOpen ? (
            <>
              <X className="h-6 w-6" />
              <span className="text-sm font-semibold pr-1">Close Copilot</span>
            </>
          ) : (
            <>
              <div className="relative">
                <Sparkles className="h-6 w-6 text-yellow-300 animate-pulse" />
                <span className="absolute -top-1 -right-1 flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75"></span>
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500"></span>
                </span>
              </div>
              <span className="text-sm font-semibold pr-1 tracking-wide">
                Stocker Copilot
              </span>
            </>
          )}
        </motion.button>
      </div>

      {/* Floating Chat Modal */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            transition={{ duration: 0.2 }}
            className="glass-panel fixed bottom-24 right-6 z-50 flex h-[min(650px,82vh)] w-[min(440px,92vw)] flex-col rounded-2xl border border-[var(--border-strong)] bg-[var(--surface)]/95 shadow-2xl backdrop-blur-xl overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between border-b border-[var(--border)] px-4 py-3 bg-[var(--surface2)]/70">
              <div className="flex items-center gap-3">
                <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 text-white shadow-md">
                  <Bot className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-[var(--text)]">
                      Stocker Copilot
                    </h3>
                    <span className="inline-flex items-center rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] font-medium text-emerald-500 border border-emerald-500/20">
                      Live AI
                    </span>
                  </div>
                  <p className="text-[11px] text-[var(--muted)]">
                    Ask in plain English or select a prompt
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-[var(--muted)] hover:text-[var(--text)]"
                  type="button"
                  onClick={handleReset}
                  title="Clear conversation"
                >
                  <RotateCcw className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 text-[var(--muted)] hover:text-[var(--text)]"
                  type="button"
                  onClick={() => setIsOpen(false)}
                  title="Minimize"
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Chat Body */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4 text-xs md:text-sm">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={cn(
                    "flex flex-col gap-1.5",
                    msg.sender === "user" ? "items-end" : "items-start"
                  )}
                >
                  <div className="flex items-center gap-1.5 px-1 text-[10px] text-[var(--muted)]">
                    {msg.sender === "user" ? (
                      <>
                        <span>You</span>
                        <User className="h-3 w-3" />
                      </>
                    ) : (
                      <>
                        <Bot className="h-3 w-3 text-blue-500" />
                        <span>Stocker Copilot</span>
                      </>
                    )}
                    <span>• {msg.time}</span>
                  </div>

                  <div
                    className={cn(
                      "max-w-[88%] rounded-2xl p-3.5 leading-relaxed shadow-sm",
                      msg.sender === "user"
                        ? "bg-blue-600 text-white rounded-tr-none"
                        : "bg-[var(--surface2)] border border-[var(--border)] text-[var(--text)] rounded-tl-none"
                    )}
                  >
                    <div className="space-y-1">
                      {renderFormattedText(msg.text)}
                    </div>

                    {/* Action Button (e.g. "Go to Inventory") */}
                    {msg.action && (
                      <div className="mt-3 pt-2.5 border-t border-[var(--border)]">
                        <Button
                          variant="primary"
                          size="sm"
                          className="w-full justify-between text-xs py-1.5 bg-blue-600 hover:bg-blue-700 text-white"
                          type="button"
                          onClick={() => {
                            navigate(msg.action!.path);
                          }}
                        >
                          <span>{msg.action.label}</span>
                          <ArrowRight className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Suggestion Chips */}
                  {msg.suggestions && msg.suggestions.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 pt-1.5 max-w-[95%]">
                      {msg.suggestions.map((sug, sIdx) => (
                        <button
                          key={sIdx}
                          type="button"
                          onClick={() => handleSendMessage(sug)}
                          disabled={loading}
                          className="inline-flex items-center gap-1 rounded-full border border-[var(--border)] bg-[var(--surface2)]/80 px-2.5 py-1 text-[11px] font-medium text-[var(--muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--text)] hover:border-blue-500/40 transition-colors duration-150 disabled:opacity-50"
                        >
                          <span>{sug}</span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}

              {/* Typing indicator */}
              {loading && (
                <div className="flex items-center gap-2 text-[var(--muted)] text-xs p-2">
                  <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-[var(--surface2)] border border-[var(--border)]">
                    <Bot className="h-4 w-4 text-blue-500 animate-pulse" />
                  </div>
                  <div className="flex items-center gap-1">
                    <span className="h-2 w-2 rounded-full bg-blue-500 animate-bounce"></span>
                    <span className="h-2 w-2 rounded-full bg-blue-500 animate-bounce [animation-delay:0.2s]"></span>
                    <span className="h-2 w-2 rounded-full bg-blue-500 animate-bounce [animation-delay:0.4s]"></span>
                  </div>
                  <span className="text-[11px] text-[var(--muted)] pl-1">
                    Querying live database & ML models...
                  </span>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>

            {/* Input Footer */}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendMessage();
              }}
              className="border-t border-[var(--border)] p-3 bg-[var(--surface2)]/50"
            >
              <div className="relative flex items-center">
                <input
                  ref={inputRef}
                  type="text"
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  placeholder="Ask a question (e.g. 'Low stock items?')..."
                  disabled={loading}
                  className="w-full rounded-xl border border-[var(--border-strong)] bg-[var(--surface)] px-3.5 py-2.5 pr-12 text-xs md:text-sm text-[var(--text)] placeholder-[var(--muted)] focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500 transition-all disabled:opacity-50"
                />
                <button
                  type="submit"
                  disabled={!input.trim() || loading}
                  className="absolute right-1.5 flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-40 disabled:pointer-events-none transition-all shadow-sm"
                  aria-label="Send query"
                >
                  <Send className="h-3.5 w-3.5" />
                </button>
              </div>
              <div className="mt-2 flex items-center justify-between px-1 text-[10px] text-[var(--muted)]">
                <span>Database-connected AI Assistant</span>
                <span>Enter ↵ to send</span>
              </div>
            </form>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
}
