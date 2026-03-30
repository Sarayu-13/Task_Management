/**
 * App.js  –  GOD COMPONENT  (intentional anti-pattern for modernisation testing)
 *
 * Issues present:
 *  - All state in one component (auth, projects, tasks, comments, notifications,
 *    search, UI state, form state, report state)
 *  - Direct fetch() calls scattered throughout event handlers – no API layer
 *  - No custom hooks – all logic inline
 *  - No component decomposition – 700+ lines in one file
 *  - Token stored in localStorage without expiry handling
 *  - No loading / error boundary strategy
 *  - Magic strings for status / priority values
 *  - Conditional rendering via long if/else chains
 *  - No form library – manual state fields for every form
 */

import React, { useState, useEffect } from 'react';
import './App.css';

const BASE_URL = 'http://localhost:5000/api';

export default function App() {
  // ── Auth state ────────────────────────────────────────────────
  const [token, setToken]           = useState(localStorage.getItem('token') || '');
  const [currentUser, setCurrentUser] = useState(
    JSON.parse(localStorage.getItem('user') || 'null')
  );

  // ── View / tab state ──────────────────────────────────────────
  const [view, setView]             = useState('login');   // login | register | dashboard | projects | tasks | profile | search | report
  const [activeProject, setActiveProject] = useState(null);
  const [activeTask, setActiveTask] = useState(null);

  // ── Data state ────────────────────────────────────────────────
  const [projects, setProjects]     = useState([]);
  const [tasks, setTasks]           = useState([]);
  const [comments, setComments]     = useState([]);
  const [users, setUsers]           = useState([]);
  const [notifications, setNotifications] = useState([]);
  const [searchResults, setSearchResults] = useState(null);
  const [report, setReport]         = useState(null);

  // ── Loading / error state ─────────────────────────────────────
  const [loading, setLoading]       = useState(false);
  const [error, setError]           = useState('');
  const [success, setSuccess]       = useState('');

  // ── Login form state ──────────────────────────────────────────
  const [loginEmail, setLoginEmail] = useState('');
  const [loginPassword, setLoginPassword] = useState('');

  // ── Register form state ───────────────────────────────────────
  const [regUsername, setRegUsername] = useState('');
  const [regEmail, setRegEmail]     = useState('');
  const [regPassword, setRegPassword] = useState('');
  const [regRole, setRegRole]       = useState('user');

  // ── Project form state ────────────────────────────────────────
  const [showProjectForm, setShowProjectForm] = useState(false);
  const [projectName, setProjectName] = useState('');
  const [projectDesc, setProjectDesc] = useState('');
  const [projectPriority, setProjectPriority] = useState('medium');
  const [projectStartDate, setProjectStartDate] = useState('');
  const [projectEndDate, setProjectEndDate]   = useState('');
  const [projectBudget, setProjectBudget]     = useState('');
  const [editingProject, setEditingProject]   = useState(null);

  // ── Task form state ───────────────────────────────────────────
  const [showTaskForm, setShowTaskForm] = useState(false);
  const [taskTitle, setTaskTitle]       = useState('');
  const [taskDesc, setTaskDesc]         = useState('');
  const [taskPriority, setTaskPriority] = useState('medium');
  const [taskStatus, setTaskStatus]     = useState('todo');
  const [taskDueDate, setTaskDueDate]   = useState('');
  const [taskEstHours, setTaskEstHours] = useState('');
  const [taskActHours, setTaskActHours] = useState('');
  const [taskAssigneeId, setTaskAssigneeId] = useState('');
  const [editingTask, setEditingTask]   = useState(null);

  // ── Comment form state ────────────────────────────────────────
  const [commentContent, setCommentContent] = useState('');

  // ── Search state ──────────────────────────────────────────────
  const [searchQuery, setSearchQuery] = useState('');

  // ── Profile edit state ────────────────────────────────────────
  const [editBio, setEditBio]   = useState('');
  const [editAvatar, setEditAvatar] = useState('');

  // ─────────────────────────────────────────────────────────────
  //  Helpers  (raw fetch repeated everywhere – no shared API client)
  // ─────────────────────────────────────────────────────────────
  const authHeaders = () => ({
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
  });

  const showMsg = (msg, isError = false) => {
    if (isError) setError(msg);
    else setSuccess(msg);
    setTimeout(() => { setError(''); setSuccess(''); }, 3000);
  };

  // ─────────────────────────────────────────────────────────────
  //  AUTH
  // ─────────────────────────────────────────────────────────────
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      // Direct fetch in event handler – no API abstraction
      const res = await fetch(`${BASE_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: loginEmail, password: loginPassword }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      setToken(data.token);
      setCurrentUser(data.user);
      localStorage.setItem('token', data.token);
      localStorage.setItem('user', JSON.stringify(data.user));
      setView('dashboard');
      loadDashboard(data.token, data.user);
    } catch (err) {
      showMsg(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/auth/register`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: regUsername, email: regEmail, password: regPassword, role: regRole }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      showMsg('Registered! Please log in.');
      setView('login');
    } catch (err) {
      showMsg(err.message, true);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    setToken('');
    setCurrentUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setView('login');
    // Resetting all state manually instead of a proper auth context reset
    setProjects([]); setTasks([]); setComments([]);
    setNotifications([]); setSearchResults(null); setReport(null);
  };

  // ─────────────────────────────────────────────────────────────
  //  DASHBOARD  (loads multiple resources inline)
  // ─────────────────────────────────────────────────────────────
  const loadDashboard = async (tkn, usr) => {
    const t = tkn || token;
    const u = usr || currentUser;
    if (!t || !u) return;
    setLoading(true);
    try {
      // Three separate fetches in one function – no Promise.all
      const pRes = await fetch(`${BASE_URL}/projects`, { headers: { Authorization: `Bearer ${t}` } });
      const pData = await pRes.json();
      setProjects(pData);

      const nRes = await fetch(`${BASE_URL}/notifications`, { headers: { Authorization: `Bearer ${t}` } });
      const nData = await nRes.json();
      setNotifications(nData);

      const uRes = await fetch(`${BASE_URL}/users`, { headers: { Authorization: `Bearer ${t}` } });
      if (uRes.ok) {
        const uData = await uRes.json();
        setUsers(uData);
      }
    } catch (err) {
      showMsg('Failed to load dashboard', true);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (token && currentUser) {
      setView('dashboard');
      loadDashboard();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ─────────────────────────────────────────────────────────────
  //  PROJECTS
  // ─────────────────────────────────────────────────────────────
  const loadProjects = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/projects`, { headers: authHeaders() });
      setProjects(await res.json());
    } catch { showMsg('Failed to load projects', true); }
    finally { setLoading(false); }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const method = editingProject ? 'PUT' : 'POST';
      const url = editingProject
        ? `${BASE_URL}/projects/${editingProject.id}`
        : `${BASE_URL}/projects`;
      const res = await fetch(url, {
        method,
        headers: authHeaders(),
        body: JSON.stringify({
          name: projectName, description: projectDesc, priority: projectPriority,
          start_date: projectStartDate, end_date: projectEndDate,
          budget: projectBudget ? parseFloat(projectBudget) : null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      showMsg(editingProject ? 'Project updated!' : 'Project created!');
      setShowProjectForm(false);
      setEditingProject(null);
      // Reset all form fields manually
      setProjectName(''); setProjectDesc(''); setProjectPriority('medium');
      setProjectStartDate(''); setProjectEndDate(''); setProjectBudget('');
      loadProjects();
    } catch (err) { showMsg(err.message, true); }
    finally { setLoading(false); }
  };

  const openEditProject = (project) => {
    setEditingProject(project);
    setProjectName(project.name); setProjectDesc(project.description || '');
    setProjectPriority(project.priority || 'medium');
    setProjectStartDate(project.start_date || ''); setProjectEndDate(project.end_date || '');
    setProjectBudget(project.budget || '');
    setShowProjectForm(true);
  };

  const handleDeleteProject = async (id) => {
    if (!window.confirm('Delete project and all its tasks?')) return;
    await fetch(`${BASE_URL}/projects/${id}`, { method: 'DELETE', headers: authHeaders() });
    showMsg('Project deleted');
    loadProjects();
  };

  const openProject = async (project) => {
    setActiveProject(project);
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/tasks?project_id=${project.id}`, { headers: authHeaders() });
      setTasks(await res.json());
      setView('tasks');
    } catch { showMsg('Failed to load tasks', true); }
    finally { setLoading(false); }
  };

  const loadProjectReport = async (projectId) => {
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/projects/${projectId}/report`, { headers: authHeaders() });
      setReport(await res.json());
      setView('report');
    } catch { showMsg('Failed to load report', true); }
    finally { setLoading(false); }
  };

  // ─────────────────────────────────────────────────────────────
  //  TASKS
  // ─────────────────────────────────────────────────────────────
  const handleCreateTask = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const method = editingTask ? 'PUT' : 'POST';
      const url = editingTask
        ? `${BASE_URL}/tasks/${editingTask.id}`
        : `${BASE_URL}/tasks`;
      const res = await fetch(url, {
        method,
        headers: authHeaders(),
        body: JSON.stringify({
          title: taskTitle, description: taskDesc, project_id: activeProject?.id,
          priority: taskPriority, status: taskStatus, due_date: taskDueDate,
          estimated_hours: taskEstHours ? parseFloat(taskEstHours) : null,
          actual_hours: taskActHours ? parseFloat(taskActHours) : null,
          assignee_id: taskAssigneeId ? parseInt(taskAssigneeId) : null,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error);
      showMsg(editingTask ? 'Task updated!' : 'Task created!');
      setShowTaskForm(false); setEditingTask(null);
      setTaskTitle(''); setTaskDesc(''); setTaskPriority('medium');
      setTaskStatus('todo'); setTaskDueDate(''); setTaskEstHours('');
      setTaskActHours(''); setTaskAssigneeId('');
      if (activeProject) openProject(activeProject);
    } catch (err) { showMsg(err.message, true); }
    finally { setLoading(false); }
  };

  const openEditTask = (task) => {
    setEditingTask(task);
    setTaskTitle(task.title); setTaskDesc(task.description || '');
    setTaskPriority(task.priority); setTaskStatus(task.status);
    setTaskDueDate(task.due_date || ''); setTaskEstHours(task.estimated_hours || '');
    setTaskActHours(task.actual_hours || ''); setTaskAssigneeId(task.assignee_id || '');
    setShowTaskForm(true);
  };

  const handleDeleteTask = async (id) => {
    if (!window.confirm('Delete task?')) return;
    await fetch(`${BASE_URL}/tasks/${id}`, { method: 'DELETE', headers: authHeaders() });
    showMsg('Task deleted');
    if (activeProject) openProject(activeProject);
  };

  const openTask = async (task) => {
    setActiveTask(task);
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/tasks/${task.id}/comments`, { headers: authHeaders() });
      setComments(await res.json());
    } catch { showMsg('Failed to load comments', true); }
    finally { setLoading(false); }
  };

  const quickUpdateStatus = async (taskId, status) => {
    await fetch(`${BASE_URL}/tasks/${taskId}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify({ status }),
    });
    if (activeProject) openProject(activeProject);
  };

  // ─────────────────────────────────────────────────────────────
  //  COMMENTS
  // ─────────────────────────────────────────────────────────────
  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!activeTask) return;
    try {
      await fetch(`${BASE_URL}/tasks/${activeTask.id}/comments`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ content: commentContent }),
      });
      setCommentContent('');
      openTask(activeTask);
    } catch { showMsg('Failed to add comment', true); }
  };

  // ─────────────────────────────────────────────────────────────
  //  NOTIFICATIONS
  // ─────────────────────────────────────────────────────────────
  const markNotifRead = async (id) => {
    await fetch(`${BASE_URL}/notifications/${id}/read`, { method: 'PUT', headers: authHeaders() });
    setNotifications(notifications.map(n => n.id === id ? { ...n, is_read: 1 } : n));
  };

  // ─────────────────────────────────────────────────────────────
  //  SEARCH
  // ─────────────────────────────────────────────────────────────
  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setLoading(true);
    try {
      const res = await fetch(`${BASE_URL}/search?q=${encodeURIComponent(searchQuery)}`, { headers: authHeaders() });
      setSearchResults(await res.json());
    } catch { showMsg('Search failed', true); }
    finally { setLoading(false); }
  };

  // ─────────────────────────────────────────────────────────────
  //  PROFILE
  // ─────────────────────────────────────────────────────────────
  const handleUpdateProfile = async (e) => {
    e.preventDefault();
    try {
      const res = await fetch(`${BASE_URL}/users/${currentUser.id}`, {
        method: 'PUT',
        headers: authHeaders(),
        body: JSON.stringify({ bio: editBio, avatar: editAvatar }),
      });
      if (!res.ok) throw new Error('Update failed');
      showMsg('Profile updated!');
    } catch (err) { showMsg(err.message, true); }
  };

  // ─────────────────────────────────────────────────────────────
  //  RENDER HELPERS  (all inlined, no sub-components)
  // ─────────────────────────────────────────────────────────────
  const priorityColor = (p) =>
    p === 'high' ? '#e74c3c' : p === 'medium' ? '#f39c12' : '#27ae60';

  const statusBadge = (s) => {
    const map = { todo: '#95a5a6', in_progress: '#3498db', done: '#27ae60', blocked: '#e74c3c' };
    return map[s] || '#95a5a6';
  };

  const unreadCount = notifications.filter(n => !n.is_read).length;

  // ─────────────────────────────────────────────────────────────
  //  RENDER
  // ─────────────────────────────────────────────────────────────
  return (
    <div className="app">
      {/* ── Navbar ── */}
      {currentUser && (
        <nav className="navbar">
          <span className="logo">TaskManager</span>
          <div className="nav-links">
            <button onClick={() => { setView('dashboard'); loadDashboard(); }}>Dashboard</button>
            <button onClick={() => { setView('projects'); loadProjects(); }}>Projects</button>
            <button onClick={() => setView('search')}>Search</button>
            <button onClick={() => setView('profile')}>Profile</button>
            <button className="notif-btn" onClick={() => setView('notifications')}>
              Notifications {unreadCount > 0 && <span className="badge">{unreadCount}</span>}
            </button>
            <button className="logout-btn" onClick={handleLogout}>Logout</button>
          </div>
          <span className="user-label">Hi, {currentUser.username} ({currentUser.role})</span>
        </nav>
      )}

      {/* ── Global messages ── */}
      {error   && <div className="alert error">{error}</div>}
      {success && <div className="alert success">{success}</div>}
      {loading && <div className="loading-bar" />}

      <div className="content">

        {/* ────────────────────── LOGIN ────────────────────── */}
        {view === 'login' && (
          <div className="auth-card">
            <h2>Sign In</h2>
            <form onSubmit={handleLogin}>
              <input placeholder="Email" type="email" value={loginEmail}
                onChange={e => setLoginEmail(e.target.value)} required />
              <input placeholder="Password" type="password" value={loginPassword}
                onChange={e => setLoginPassword(e.target.value)} required />
              <button type="submit" disabled={loading}>Login</button>
            </form>
            <p>No account? <button className="link-btn" onClick={() => setView('register')}>Register</button></p>
          </div>
        )}

        {/* ────────────────────── REGISTER ────────────────────── */}
        {view === 'register' && (
          <div className="auth-card">
            <h2>Create Account</h2>
            <form onSubmit={handleRegister}>
              <input placeholder="Username" value={regUsername}
                onChange={e => setRegUsername(e.target.value)} required />
              <input placeholder="Email" type="email" value={regEmail}
                onChange={e => setRegEmail(e.target.value)} required />
              <input placeholder="Password" type="password" value={regPassword}
                onChange={e => setRegPassword(e.target.value)} required />
              <select value={regRole} onChange={e => setRegRole(e.target.value)}>
                <option value="user">User</option>
                <option value="admin">Admin</option>
              </select>
              <button type="submit" disabled={loading}>Register</button>
            </form>
            <p>Have an account? <button className="link-btn" onClick={() => setView('login')}>Login</button></p>
          </div>
        )}

        {/* ────────────────────── DASHBOARD ────────────────────── */}
        {view === 'dashboard' && (
          <div>
            <h2>Dashboard</h2>
            <div className="stats-row">
              <div className="stat-card"><h3>{projects.length}</h3><p>Projects</p></div>
              <div className="stat-card">
                <h3>{projects.reduce((s, p) => s + (p.task_count || 0), 0)}</h3><p>Total Tasks</p>
              </div>
              <div className="stat-card">
                <h3>{projects.reduce((s, p) => s + (p.completed_tasks || 0), 0)}</h3><p>Done</p>
              </div>
              <div className="stat-card"><h3>{unreadCount}</h3><p>Notifications</p></div>
            </div>
            <h3>Recent Projects</h3>
            <div className="project-grid">
              {projects.slice(0, 4).map(p => (
                <div key={p.id} className="project-card" onClick={() => openProject(p)}>
                  <h4>{p.name}</h4>
                  <p>{p.description}</p>
                  <span className="tag" style={{ background: priorityColor(p.priority) }}>{p.priority}</span>
                  <span className="tag" style={{ background: statusBadge(p.status) }}>{p.status}</span>
                  <p className="small">{p.completed_tasks}/{p.task_count} tasks done</p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ────────────────────── PROJECTS ────────────────────── */}
        {view === 'projects' && (
          <div>
            <div className="section-header">
              <h2>Projects</h2>
              <button onClick={() => { setShowProjectForm(true); setEditingProject(null); }}>+ New Project</button>
            </div>

            {showProjectForm && (
              <div className="form-card">
                <h3>{editingProject ? 'Edit Project' : 'New Project'}</h3>
                <form onSubmit={handleCreateProject}>
                  <input placeholder="Project Name" value={projectName}
                    onChange={e => setProjectName(e.target.value)} required />
                  <textarea placeholder="Description" value={projectDesc}
                    onChange={e => setProjectDesc(e.target.value)} />
                  <select value={projectPriority} onChange={e => setProjectPriority(e.target.value)}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                  <input type="date" placeholder="Start Date" value={projectStartDate}
                    onChange={e => setProjectStartDate(e.target.value)} />
                  <input type="date" placeholder="End Date" value={projectEndDate}
                    onChange={e => setProjectEndDate(e.target.value)} />
                  <input type="number" placeholder="Budget" value={projectBudget}
                    onChange={e => setProjectBudget(e.target.value)} />
                  <div className="form-actions">
                    <button type="submit">{editingProject ? 'Update' : 'Create'}</button>
                    <button type="button" onClick={() => { setShowProjectForm(false); setEditingProject(null); }}>Cancel</button>
                  </div>
                </form>
              </div>
            )}

            <div className="project-grid">
              {projects.map(p => (
                <div key={p.id} className="project-card">
                  <h4 onClick={() => openProject(p)} style={{ cursor: 'pointer' }}>{p.name}</h4>
                  <p>{p.description}</p>
                  <span className="tag" style={{ background: priorityColor(p.priority) }}>{p.priority}</span>
                  <span className="tag" style={{ background: statusBadge(p.status) }}>{p.status}</span>
                  {p.budget && <p className="small">Budget: ${p.budget}</p>}
                  <p className="small">Owner: {p.owner_name} | Tasks: {p.task_count}</p>
                  <div className="card-actions">
                    <button onClick={() => openProject(p)}>Open</button>
                    <button onClick={() => loadProjectReport(p.id)}>Report</button>
                    <button onClick={() => openEditProject(p)}>Edit</button>
                    <button className="danger" onClick={() => handleDeleteProject(p.id)}>Delete</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ────────────────────── TASKS ────────────────────── */}
        {view === 'tasks' && activeProject && (
          <div>
            <div className="section-header">
              <div>
                <button className="back-btn" onClick={() => { setView('projects'); loadProjects(); }}>← Back</button>
                <h2>{activeProject.name} – Tasks</h2>
              </div>
              <button onClick={() => { setShowTaskForm(true); setEditingTask(null); }}>+ New Task</button>
            </div>

            {showTaskForm && (
              <div className="form-card">
                <h3>{editingTask ? 'Edit Task' : 'New Task'}</h3>
                <form onSubmit={handleCreateTask}>
                  <input placeholder="Task Title" value={taskTitle}
                    onChange={e => setTaskTitle(e.target.value)} required />
                  <textarea placeholder="Description" value={taskDesc}
                    onChange={e => setTaskDesc(e.target.value)} />
                  <select value={taskPriority} onChange={e => setTaskPriority(e.target.value)}>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                  <select value={taskStatus} onChange={e => setTaskStatus(e.target.value)}>
                    <option value="todo">To Do</option>
                    <option value="in_progress">In Progress</option>
                    <option value="done">Done</option>
                    <option value="blocked">Blocked</option>
                  </select>
                  <input type="date" value={taskDueDate} onChange={e => setTaskDueDate(e.target.value)} />
                  <input type="number" placeholder="Estimated Hours" value={taskEstHours}
                    onChange={e => setTaskEstHours(e.target.value)} />
                  <input type="number" placeholder="Actual Hours" value={taskActHours}
                    onChange={e => setTaskActHours(e.target.value)} />
                  <select value={taskAssigneeId} onChange={e => setTaskAssigneeId(e.target.value)}>
                    <option value="">Unassigned</option>
                    {users.map(u => <option key={u.id} value={u.id}>{u.username}</option>)}
                  </select>
                  <div className="form-actions">
                    <button type="submit">{editingTask ? 'Update' : 'Create'}</button>
                    <button type="button" onClick={() => { setShowTaskForm(false); setEditingTask(null); }}>Cancel</button>
                  </div>
                </form>
              </div>
            )}

            {/* Kanban-style columns – all inline */}
            <div className="kanban">
              {['todo', 'in_progress', 'done', 'blocked'].map(col => (
                <div key={col} className="kanban-col">
                  <h4 className="col-header" style={{ background: statusBadge(col) }}>
                    {col.replace('_', ' ').toUpperCase()}
                  </h4>
                  {tasks.filter(t => t.status === col).map(task => (
                    <div key={task.id} className="task-card">
                      <h5 onClick={() => openTask(task)} style={{ cursor: 'pointer' }}>{task.title}</h5>
                      <span className="tag" style={{ background: priorityColor(task.priority) }}>{task.priority}</span>
                      {task.due_date && <p className="small">Due: {task.due_date}</p>}
                      {task.assignee_name && <p className="small">Assignee: {task.assignee_name}</p>}
                      {task.estimated_hours && (
                        <p className="small">Est: {task.estimated_hours}h / Act: {task.actual_hours || 0}h</p>
                      )}
                      <div className="card-actions">
                        {col !== 'in_progress' && (
                          <button onClick={() => quickUpdateStatus(task.id, 'in_progress')}>▶</button>
                        )}
                        {col !== 'done' && (
                          <button onClick={() => quickUpdateStatus(task.id, 'done')}>✓</button>
                        )}
                        <button onClick={() => openEditTask(task)}>Edit</button>
                        <button className="danger" onClick={() => handleDeleteTask(task.id)}>Del</button>
                      </div>
                    </div>
                  ))}
                </div>
              ))}
            </div>

            {/* Task detail panel */}
            {activeTask && (
              <div className="task-detail">
                <div className="section-header">
                  <h3>{activeTask.title}</h3>
                  <button onClick={() => setActiveTask(null)}>✕</button>
                </div>
                <p>{activeTask.description}</p>
                <h4>Comments</h4>
                <div className="comments">
                  {comments.map(c => (
                    <div key={c.id} className="comment">
                      <strong>{c.username}</strong>
                      <span className="small"> {c.created_at}</span>
                      <p>{c.content}</p>
                    </div>
                  ))}
                </div>
                <form onSubmit={handleAddComment} className="comment-form">
                  <input placeholder="Add a comment…" value={commentContent}
                    onChange={e => setCommentContent(e.target.value)} required />
                  <button type="submit">Post</button>
                </form>
              </div>
            )}
          </div>
        )}

        {/* ────────────────────── SEARCH ────────────────────── */}
        {view === 'search' && (
          <div>
            <h2>Search</h2>
            <form onSubmit={handleSearch} className="search-form">
              <input placeholder="Search tasks and projects…" value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)} />
              <button type="submit">Search</button>
            </form>
            {searchResults && (
              <div>
                <h3>Results ({searchResults.total})</h3>
                {searchResults.projects.length > 0 && (
                  <div>
                    <h4>Projects</h4>
                    {searchResults.projects.map(p => (
                      <div key={p.id} className="result-item" onClick={() => openProject(p)}>
                        <span className="tag">project</span> {p.name}
                      </div>
                    ))}
                  </div>
                )}
                {searchResults.tasks.length > 0 && (
                  <div>
                    <h4>Tasks</h4>
                    {searchResults.tasks.map(t => (
                      <div key={t.id} className="result-item">
                        <span className="tag">task</span> {t.name}
                      </div>
                    ))}
                  </div>
                )}
                {searchResults.total === 0 && <p>No results found.</p>}
              </div>
            )}
          </div>
        )}

        {/* ────────────────────── NOTIFICATIONS ────────────────────── */}
        {view === 'notifications' && (
          <div>
            <h2>Notifications</h2>
            {notifications.length === 0 && <p>No notifications.</p>}
            {notifications.map(n => (
              <div key={n.id} className={`notif-item ${n.is_read ? 'read' : 'unread'}`}>
                <p>{n.message}</p>
                <span className="small">{n.created_at}</span>
                {!n.is_read && (
                  <button onClick={() => markNotifRead(n.id)}>Mark read</button>
                )}
              </div>
            ))}
          </div>
        )}

        {/* ────────────────────── PROFILE ────────────────────── */}
        {view === 'profile' && currentUser && (
          <div className="profile-card">
            <h2>Profile</h2>
            <p><strong>Username:</strong> {currentUser.username}</p>
            <p><strong>Email:</strong> {currentUser.email}</p>
            <p><strong>Role:</strong> {currentUser.role}</p>
            <h3>Edit Profile</h3>
            <form onSubmit={handleUpdateProfile}>
              <textarea placeholder="Bio" value={editBio} onChange={e => setEditBio(e.target.value)} />
              <input placeholder="Avatar URL" value={editAvatar} onChange={e => setEditAvatar(e.target.value)} />
              <button type="submit">Save</button>
            </form>
          </div>
        )}

        {/* ────────────────────── REPORT ────────────────────── */}
        {view === 'report' && report && (
          <div>
            <button className="back-btn" onClick={() => { setView('projects'); loadProjects(); }}>← Back</button>
            <h2>Project Report: {report.project?.name}</h2>
            <div className="stats-row">
              <div className="stat-card"><h3>{report.total_tasks}</h3><p>Total Tasks</p></div>
              <div className="stat-card"><h3>{report.completed_tasks}</h3><p>Completed</p></div>
              <div className="stat-card"><h3>{report.in_progress_tasks}</h3><p>In Progress</p></div>
              <div className="stat-card"><h3>{report.overdue_tasks}</h3><p>Overdue</p></div>
              <div className="stat-card"><h3>{report.completion_rate}%</h3><p>Completion Rate</p></div>
              <div className="stat-card">
                <h3>{report.total_estimated_hours}h</h3><p>Est. Hours</p>
              </div>
              <div className="stat-card">
                <h3>{report.total_actual_hours}h</h3><p>Actual Hours</p>
              </div>
            </div>
            <p className="small">Generated at: {report.generated_at}</p>
          </div>
        )}

      </div>
    </div>
  );
}
