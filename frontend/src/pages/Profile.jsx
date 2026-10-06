import React, { useEffect, useState } from 'react';
import api from '../utils/api';

export default function ProfilePage() {
  const [profile, setProfile] = useState(null);
  const [error, setError] = useState("");

  const load = async () => {
    setError("");
    try {
      const res = await api.get('/auth/me');
      setProfile(res.data);
    } catch (err) {
      console.error('Could not load profile', err);
      setError(err?.response?.data?.detail || 'Could not load your profile. Please try again.');
    }
  };

  useEffect(() => {
    load();
  }, []);

  if (!profile) {
    return (
      <div className="panel">
        {error ? (
          <div className="error-box" role="alert">
            {error}
            <button className="button secondary small" onClick={load}>Retry</button>
          </div>
        ) : <div className="loading-box">Loading profile...</div>}
      </div>
    );
  }

  return (
    <div className="panel">
      <h3>Profile</h3>
      <div className="profile-grid">
        <div><strong>Full name</strong><div>{profile.full_name || '—'}</div></div>
        <div><strong>Username</strong><div>{profile.username}</div></div>
        <div><strong>Email</strong><div>{profile.email}</div></div>
        <div><strong>Joined</strong><div>{new Date(profile.created_at).toLocaleDateString()}</div></div>
      </div>
    </div>
  );
}
