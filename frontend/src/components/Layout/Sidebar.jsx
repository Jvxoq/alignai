import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import { useSession } from "../../hooks/useSession";

export default function Sidebar() {
  const [showDeleteModal, setShowDeleteModal] = useState(null);
  const [deleteError, setDeleteError] = useState(null);
  const { logout } = useAuth();
  const { sessionId, sessions, isLoading, createSession, clearSession, deleteSession, setActiveSession } = useSession();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate("/login");
  };

  const handleDelete = async (id) => {
    setDeleteError(null);
    setShowDeleteModal(null);
    const success = await deleteSession(id);
    if (!success) {
      setDeleteError("Failed to delete session. Please try again.");
    }
  };

  return (
    <aside className="sidebar">
      <div className="sidebar-header">
        <h2>AlignAI</h2>
      </div>
      <div className="sidebar-sessions">
        <div className="sidebar-session-header">
          <h3>Sessions</h3>
          <button className="new-session-button" onClick={clearSession} disabled={isLoading}>
            + New Session
          </button>
        </div>
        {isLoading ? (
          <div className="loading">Loading...</div>
        ) : sessions.length === 0 ? (
          <div className="no-sessions">
            <p>No sessions yet</p>
            <button onClick={createSession}>Create your first session</button>
          </div>
        ) : (
          <ul className="session-list">
            {sessions.map((session) => (
              <li key={session.id} className={`session-item ${sessionId === session.id ? "active" : ""}`}>
                <button
                  className="session-name"
                  onClick={() => setActiveSession(session.id)}
                  title={session.title || "Untitled session"}
                >
                  {session.title || "Untitled session"}
                </button>
                <button
                  className="session-delete"
                  onClick={() => {
                    setDeleteError(null);
                    setShowDeleteModal(session.id);
                  }}
                  aria-label="Delete session"
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div className="sidebar-footer">
        <button className="logout-button" onClick={handleLogout}>
          Sign Out
        </button>
      </div>

      {showDeleteModal && (
        <div className="modal-overlay" onClick={() => setShowDeleteModal(null)}>
          <div className="modal modal-small" onClick={(e) => e.stopPropagation()}>
            <h3>Delete Session</h3>
            <p>Are you sure you want to delete this session? This action cannot be undone.</p>
            {deleteError && <div className="modal-error">{deleteError}</div>}
            <div className="modal-actions">
              <button className="modal-button secondary" onClick={() => setShowDeleteModal(null)}>
                Cancel
              </button>
              <button className="modal-button danger" onClick={() => handleDelete(showDeleteModal)}>
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}