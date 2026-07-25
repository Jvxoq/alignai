import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { useAuth } from "../../hooks/useAuth";
import { useSession } from "../../hooks/useSession";
import DeleteAccountModal from "../Auth/DeleteAccountModal";
import PressButton from "../motion/PressButton";
import { duration, easeStandard, springs, staggerStep } from "../../lib/motion";

// Container/item variants for the staggered session-list reveal. Triggers
// once per Sidebar mount (initial="hidden" -> animate="show"), not on every
// re-render -- selecting a session doesn't replay the stagger.
const listVariants = {
  hidden: {},
  show: { transition: { staggerChildren: staggerStep } },
};
const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: springs.card },
};

export default function Sidebar() {
  const [showDeleteModal, setShowDeleteModal] = useState(null);
  const [showDeleteAccount, setShowDeleteAccount] = useState(false);
  const [deleteError, setDeleteError] = useState(null);
  const { logout } = useAuth();
  const { sessionId, sessions, isLoading, createSession, clearSession, deleteSession, setActiveSession } = useSession();
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();

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
          <PressButton className="new-session-button" onClick={clearSession} disabled={isLoading}>
            + New Session
          </PressButton>
        </div>
        {isLoading ? (
          <div className="session-skeleton" role="status">
            <span className="sr-only">Loading sessions...</span>
            <div className="session-skeleton-item" />
            <div className="session-skeleton-item" />
            <div className="session-skeleton-item" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="no-sessions">
            <p>No sessions yet</p>
            <PressButton onClick={createSession}>Create your first session</PressButton>
          </div>
        ) : (
          <motion.ul className="session-list" variants={listVariants} initial="hidden" animate="show">
            {sessions.map((session) => (
              <motion.li
                key={session.id}
                className={`session-item ${sessionId === session.id ? "active" : ""}`}
                variants={itemVariants}
              >
                <PressButton
                  className="session-name"
                  onClick={() => setActiveSession(session.id)}
                  title={session.title || "Untitled session"}
                >
                  {session.title || "Untitled session"}
                </PressButton>
                <PressButton
                  className="session-delete"
                  onClick={() => {
                    setDeleteError(null);
                    setShowDeleteModal(session.id);
                  }}
                  aria-label="Delete session"
                >
                  ×
                </PressButton>
              </motion.li>
            ))}
          </motion.ul>
        )}
      </div>
      <div className="sidebar-footer">
        <PressButton className="logout-button" onClick={handleLogout}>
          Sign Out
        </PressButton>
        <PressButton className="delete-account-button" onClick={() => setShowDeleteAccount(true)}>
          Delete Account
        </PressButton>
      </div>

      {showDeleteModal && (
        <motion.div
          className="modal-overlay"
          onClick={() => setShowDeleteModal(null)}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: duration.fast, ease: easeStandard }}
        >
          <motion.div
            className="modal modal-small"
            onClick={(e) => e.stopPropagation()}
            initial={{ opacity: 0, y: reduceMotion ? 0 : 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={springs.standard}
          >
            <h3>Delete Session</h3>
            <p>Are you sure you want to delete this session? This action cannot be undone.</p>
            {deleteError && <div className="modal-error">{deleteError}</div>}
            <div className="modal-actions">
              <PressButton className="modal-button secondary" onClick={() => setShowDeleteModal(null)}>
                Cancel
              </PressButton>
              <PressButton className="modal-button danger" onClick={() => handleDelete(showDeleteModal)}>
                Delete
              </PressButton>
            </div>
          </motion.div>
        </motion.div>
      )}

      <DeleteAccountModal isOpen={showDeleteAccount} onClose={() => setShowDeleteAccount(false)} />
    </aside>
  );
}