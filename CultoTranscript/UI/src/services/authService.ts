import axios from 'axios';
import { config } from '../lib/config';

const api = axios.create({
    baseURL: config.apiBaseUrl,
    headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
    },
    withCredentials: true,
});

export interface LoginCredentials {
    email: string;
    password: string;
}

export interface RegisterData {
    email: string;
    password: string;
    church_name: string;
    subdomain?: string;
    invite_token?: string;
}

class AuthService {
    async login(credentials: LoginCredentials): Promise<boolean> {
        const formData = new URLSearchParams();
        formData.append('email', credentials.email);
        formData.append('password', credentials.password);

        try {
            // The backend redirects on success, so we need to handle that or check response
            // For now, we'll assume 200/302 means success if we don't get an error page
            await api.post('/login', formData, {
                maxRedirects: 0, // Don't follow redirects automatically to detect 302
                validateStatus: (status) => status >= 200 && status < 400,
            });

            return true;
        } catch (error: any) {
            if (error.response?.status === 302 || error.response?.status === 303) {
                return true; // Redirect means success
            }
            throw new Error('Login failed');
        }
    }

    async register(data: RegisterData): Promise<boolean> {
        const formData = new URLSearchParams();
        formData.append('email', data.email);
        formData.append('password', data.password);
        formData.append('church_name', data.church_name);
        if (data.subdomain) {
            formData.append('subdomain', data.subdomain);
        } else {
            formData.append('subdomain', ''); // Backend expects this field
        }
        if (data.invite_token) {
            formData.append('invite_token', data.invite_token);
        }

        try {
            await api.post('/register', formData, {
                maxRedirects: 0,
                validateStatus: (status) => status >= 200 && status < 400,
            });
            return true;
        } catch (error: any) {
            if (error.response?.status === 302 || error.response?.status === 303) {
                return true;
            }
            throw new Error('Registration failed');
        }
    }

    async logout(): Promise<void> {
        await api.get('/logout');
    }
}

export const authService = new AuthService();
