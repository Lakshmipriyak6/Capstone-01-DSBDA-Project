import React from 'react';

export default function SettingsPage({ theme, setTheme }) {
  return (
    <div className="panel">
      <h3>Settings</h3>
      <div className="settings-row">
        <label>Appearance</label>
        <div>
          <button className="button" onClick={() => setTheme('light')}>Light</button>
          <button className="button" onClick={() => setTheme('dark')}>Dark</button>
          <button className="button" onClick={() => setTheme(window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')}>System</button>
        </div>
      </div>

      <div className="settings-row">
        <label>Account</label>
        <div>Manage account settings from the profile page.</div>
      </div>
    </div>
  );
}
