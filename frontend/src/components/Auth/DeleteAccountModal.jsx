import { useState } from "react";
import { useAuth } from "../../hooks/useAuth";
import { useNavigate } from "react-router-dom";

export default function DeleteAccountModal({ isOpen, onClose }) {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const { deleteAccount } = useAuth();
  const navigate = useNavigate();

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
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Delete Account</h3>
        <p>This action is irreversible. All your data and sessions will be permanently deleted.</p>
        {error && <div className="modal-error">{error}</div>}
        <div className="modal-actions">
          <button className="modal-button secondary" onClick={onClose} disabled={isLoading}>
            Cancel
          </button>
          <button className="modal-button danger" onClick={handleConfirm} disabled={isLoading}>
            {isLoading ? "Deleting..." : "Delete Account"}
          </button>
        </div>
      </div>
    </div>
  );
}