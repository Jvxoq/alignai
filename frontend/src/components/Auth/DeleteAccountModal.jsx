import { useState } from "react";
import { motion, useReducedMotion } from "motion/react";
import { useAuth } from "../../hooks/useAuth";
import { useNavigate } from "react-router-dom";
import PressButton from "../motion/PressButton";
import { duration, easeStandard, springs } from "../../lib/motion";

export default function DeleteAccountModal({ isOpen, onClose }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const { deleteAccount } = useAuth();
  const navigate = useNavigate();
  const reduceMotion = useReducedMotion();

  const handleConfirm = async () => {
    setError("");
    setIsLoading(true);

    try {
      const success = await deleteAccount();
      if (success) {
        navigate("/signup");
        onClose();
      } else {
        setError("Failed to delete account. Please try again.");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <motion.div
      className="modal-overlay"
      onClick={onClose}
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: duration.fast, ease: easeStandard }}
    >
      <motion.div
        className="modal"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, y: reduceMotion ? 0 : 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={springs.standard}
      >
        <h3>Delete Account</h3>
        <p>This action is irreversible. All your data and sessions will be permanently deleted.</p>
        {error && <div className="modal-error">{error}</div>}
        <div className="modal-actions">
          <PressButton className="modal-button secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </PressButton>
          <PressButton className="modal-button danger" onClick={handleConfirm} disabled={isLoading}>
            {isLoading ? "Deleting..." : "Delete Account"}
          </PressButton>
        </div>
      </motion.div>
    </motion.div>
  );
}