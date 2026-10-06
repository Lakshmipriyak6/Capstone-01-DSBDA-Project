import axios from 'axios';

const API_URL = import.meta.env.VITE_API_URL || '';
const api = axios.create({ baseURL: API_URL });

// helper to set / clear auth token and persist it
export function setAuthToken(token) {
	if (token) {
		api.defaults.headers.common.Authorization = `Bearer ${token}`;
		localStorage.setItem('documind_token', token);
	} else {
		delete api.defaults.headers.common.Authorization;
		localStorage.removeItem('documind_token');
	}
}

// initialize from storage if present
const stored = localStorage.getItem('documind_token');
if (stored) api.defaults.headers.common.Authorization = `Bearer ${stored}`;

export default api;
