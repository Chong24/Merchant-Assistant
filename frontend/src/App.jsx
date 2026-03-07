import { useState, useRef, useEffect } from 'react';
import { Send, UploadCloud, Database, MessagesSquare, CheckCircle, Store, Layers, X } from 'lucide-react';
import './App.css';

function App() {
  const [messages, setMessages] = useState([
    {
      role: 'ai',
      content: '你好！我是你的商户智能助手。我可以查阅操作指南(RAG)或调取经营数据(DB)，并且给出针对性的建议，今天需要点什么？',
      route: '欢迎语'
    }
  ]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [notification, setNotification] = useState('');

  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [isLoggedIn, setIsLoggedIn] = useState(!!localStorage.getItem('token'));
  const [authMode, setAuthMode] = useState('login'); // 'login' or 'register'
  const [authData, setAuthData] = useState({ username: '', password: '', merchant_name: '' });
  const [isAuthLoading, setIsAuthLoading] = useState(false);

  // 飞轮数据相关状态（回归修复：之前误删导致白屏）
  const [showFlywheel, setShowFlywheel] = useState(false);
  const [pendingQA, setPendingQA] = useState([]);
  const [answers, setAnswers] = useState({});

  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const abortControllerRef = useRef(null);

  const API_BASE = 'http://localhost:8000'; // FastAPI 后端地址

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const showNotification = (msg) => {
    setNotification(''); // 先清空，确保重复触发动画
    setTimeout(() => {
      setNotification(msg);
      setTimeout(() => setNotification(''), 4000);
    }, 50);
  };

  const handleAuth = async (e) => {
    e.preventDefault();
    const endpoint = authMode === 'login' ? '/login' : '/register';
    setIsAuthLoading(true);
    setNotification(''); // 开始认证前清空旧通知
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(authData),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '认证失败');

      if (authMode === 'login') {
        localStorage.setItem('token', data.access_token);
        setToken(data.access_token);
        setIsLoggedIn(true);
        // 1. 登录成功：重置对话历史，展示该商户的专属欢迎语
        setMessages([
          {
            role: 'ai',
            content: `你好！登录成功。我是商户智能助手，已为你切换至【商户号：${data.merchant_no}】的专属数据沙箱。今天有什么可以帮您？`,
            route: '欢迎语'
          }
        ]);
        showNotification('登录成功！已进入安全数据环境。');
      } else {
        // 2. 注册成功：切换回登录界面
        setAuthMode('login');
        setAuthData(prev => ({ ...prev, password: '' }));
        showNotification('注册成功，请使用新账号登录！');
      }
    } catch (error) {
      showNotification(error.message);
    } finally {
      setIsAuthLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    setToken('');
    setIsLoggedIn(false);
    setMessages([{ role: 'ai', content: '已安全退出登录。', route: 'System' }]);
    showNotification('已成功退出登录');
  };

  const handleSend = async () => {
    if (!inputValue.trim()) return;

    const userMessage = { role: 'human', content: inputValue };
    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setIsLoading(true);

    // 初始化 AbortController 用于停止功能
    abortControllerRef.current = new AbortController();

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({ query: userMessage.content, session_id: 'default' }),
        signal: abortControllerRef.current.signal // 绑定信号
      });

      if (response.status === 401) {
        handleLogout();
        throw new Error('会话已过期，请重新登录');
      }

      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || '后端请求失败');

      const aiContent = data.messages.join('\n\n');
      const aiMessage = {
        role: 'ai',
        content: aiContent || '网络波动，请重试。',
        route: data.final_route,
      };
      setMessages((prev) => [...prev, aiMessage]);

      if (aiContent === '网络波动，请重试。') {
        showNotification('请求遇到小问题，请稍后再试');
      }
    } catch (error) {
      if (error.name === 'AbortError') {
        setMessages((prev) => [
          ...prev,
          { role: 'ai', content: '已停止生成。', route: 'System' }
        ]);
      } else {
        console.error(error);
        setMessages((prev) => [
          ...prev,
          { role: 'ai', content: `错误: ${error.message}`, route: 'error' }
        ]);
      }
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  };

  const handleStop = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    setIsUploading(true);
    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: 'POST',
        body: formData,
      });

      if (!response.ok) throw new Error('上传失败');

      const data = await response.json();
      showNotification(`成功录入 ${data.chunks_added} 条知识！`);
    } catch (error) {
      console.error(error);
      showNotification('知识库文件处理失败！');
    } finally {
      setIsUploading(false);
      // 清空 file input 的值以允许重复选择同一文件
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const loadPendingQA = async () => {
    try {
      const res = await fetch(`${API_BASE}/pending_questions`);
      const data = await res.json();
      setPendingQA(data);
    } catch (e) {
      console.error(e);
    }
  };

  const openFlywheel = () => {
    setShowFlywheel(true);
    loadPendingQA();
  };

  const handleApprove = async (id, question) => {
    const answer = answers[id];
    if (!answer || !answer.trim()) return;
    try {
      await fetch(`${API_BASE}/approve_question`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id, question, answer })
      });
      showNotification('数据飞轮已入库，知识库更新！');
      loadPendingQA();
      setAnswers(prev => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    } catch (e) {
      console.error(e);
      showNotification('入库失败');
    }
  };

  const handleDismiss = async (id) => {
    try {
      await fetch(`${API_BASE}/delete_question/${id}`, { method: 'DELETE' });
      setPendingQA(prev => prev.filter(q => q.id !== id));
    } catch (e) {
      console.error(e);
      showNotification('删除失败');
    }
  };

  return (
    <div className="app-container">
      {/* 侧边栏 */}
      <div className="sidebar glass-panel">
        <h1>
          <Store className="text-blue-500" />
          商户智能助手
        </h1>

        <div className="upload-section mt-8">
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileUpload}
            className="upload-input"
            accept=".pdf,.txt,.md,.csv"
          />
          {isUploading ? (
            <div className="flex flex-col items-center">
              <UploadCloud className="upload-icon uploading-spinner" size={32} />
              <span className="upload-text text-blue-400 mt-2">向量化处理中...</span>
            </div>
          ) : (
            <div className="flex flex-col items-center">
              <UploadCloud className="upload-icon" size={32} />
              <span className="upload-text">点击上传商户知识文档</span>
              <span className="text-xs text-slate-500 mt-2">支持 PDF, TXT, MD</span>
            </div>
          )}
        </div>

        <div className="upload-section mt-4" onClick={openFlywheel} style={{ borderColor: 'rgba(192, 132, 252, 0.4)' }}>
          <div className="flex flex-col items-center">
            <Layers className="upload-icon text-purple-400" size={32} />
            <span className="upload-text text-purple-200 mt-2">数据飞轮 (人工审核)</span>
            <span className="text-xs text-slate-500 mt-2">打通低置信度异常回复闭环</span>
          </div>
        </div>

        <div className="features-list">
          <h3>多智能体系统特性</h3>
          <div className="feature-item">
            <MessagesSquare size={16} />
            LLM 动态意图路由分发
          </div>
          <div className="feature-item">
            <Database size={16} />
            数据库 Text-to-SQL
          </div>
          <div className="feature-item">
            <CheckCircle size={16} />
            商户数据物理隔离
          </div>
        </div>

        {isLoggedIn && (
          <button className="auth-btn logout mt-4" onClick={handleLogout}>退出登录</button>
        )}
      </div>

      {!isLoggedIn && (
        <div className="auth-overlay">
          <form className="auth-form glass-panel" onSubmit={handleAuth}>
            <h2>{authMode === 'login' ? '商户登录' : '新商户注册'}</h2>
            <div className="input-group">
              <label>用户名</label>
              <input
                type="text"
                required
                value={authData.username}
                onChange={e => setAuthData({ ...authData, username: e.target.value })}
              />
            </div>
            <div className="input-group">
              <label>密码</label>
              <input
                type="password"
                required
                value={authData.password}
                onChange={e => setAuthData({ ...authData, password: e.target.value })}
              />
            </div>
            {authMode === 'register' && (
              <div className="input-group">
                <label>商户显示名称</label>
                <input
                  type="text"
                  required
                  value={authData.merchant_name}
                  onChange={e => setAuthData({ ...authData, merchant_name: e.target.value })}
                />
              </div>
            )}
            <button className="auth-submit-btn" type="submit" disabled={isAuthLoading}>
              {isAuthLoading ? (
                <div className="flex items-center justify-center gap-2">
                  <div className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                  处理中...
                </div>
              ) : (
                authMode === 'login' ? '登录' : '注册'
              )}
            </button>
            <p className="auth-toggle" onClick={() => setAuthMode(authMode === 'login' ? 'register' : 'login')}>
              {authMode === 'login' ? '没有账号？去注册' : '已有账号？去登录'}
            </p>
          </form>
        </div>
      )}


      {/* 主聊天区 */}
      <main className="chat-main">
        <div className="chat-header glass-panel border-l-0 border-r-0 border-t-0">
          <div className="flex items-center gap-3">
            <div className="online-indicator">
              <div className="dot"></div>
              <span>Multi-Agent 系统在线</span>
            </div>
          </div>
        </div>

        <div className="messages-container">
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="avatar">
                {msg.role === 'human' ? 'Me' : 'AI'}
              </div>
              <div>
                <div className="message-bubble">
                  {msg.content}
                </div>
                {msg.role === 'ai' && msg.route && (
                  <div className="route-badge">
                    最终流转: {msg.route}
                  </div>
                )}
              </div>
            </div>
          ))}

          {isLoading && (
            <div className="message ai">
              <div className="avatar">AI</div>
              <div className="message-bubble typing-indicator">
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
                <div className="typing-dot"></div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="input-area">
          <div className="input-container glass-panel bg-opacity-50">
            <textarea
              className="chat-input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题，例如：查询今日营业额 或 上传入驻指南..."
              rows={1}
            />
            <button
              className="send-btn"
              onClick={handleSend}
              disabled={isLoading || !inputValue.trim()}
            >
              <Send size={20} />
            </button>
            {isLoading && (
              <button className="stop-btn" onClick={handleStop} title="停止生成">
                <X size={20} />
              </button>
            )}
          </div>
          <div className="text-center mt-3 text-xs text-slate-500">
            此助手由 LangGraph Supervisor 框架提供驱动
          </div>
        </div>
      </main>

      {notification && (
        <div className="notification">
          <CheckCircle size={20} />
          {notification}
        </div>
      )}

      {/* 弹窗：数据飞轮管理 */}
      {showFlywheel && (
        <div className="flywheel-modal-overlay">
          <div className="flywheel-modal glass-panel">
            <div className="flywheel-header">
              <h2>人工审核 / 数据落地飞轮</h2>
              <button onClick={() => setShowFlywheel(false)}><X size={20} /></button>
            </div>
            <div className="flywheel-content">
              {pendingQA.length === 0 ? (
                <div className="text-center text-slate-400 py-10">当前没有需要人工审核的失效问题。</div>
              ) : (
                pendingQA.map(qa => (
                  <div key={qa.id} className="flywheel-card">
                    <div className="flywheel-card-header">
                      <div>
                        <p className="text-sm"><strong>用户原问题:</strong> {qa.original}</p>
                        <p className="text-purple-400 mt-2"><strong>AI提炼总结:</strong> {qa.refined}</p>
                      </div>
                      <button
                        className="dismiss-btn"
                        onClick={() => handleDismiss(qa.id)}
                        title="删除这条问题"
                      >
                        <X size={16} />
                      </button>
                    </div>
                    <textarea
                      placeholder="作为专员，请输入标准答案以供下次 RAG 召回..."
                      className="flywheel-input mt-3"
                      value={answers[qa.id] || ''}
                      onChange={e => setAnswers({ ...answers, [qa.id]: e.target.value })}
                    />
                    <div className="flex justify-end mt-3">
                      <button className="approve-btn" onClick={() => handleApprove(qa.id, qa.refined)}>
                        提交入库
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
