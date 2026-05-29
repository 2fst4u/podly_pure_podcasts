import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { authApi } from '../services/api';
import type { AuthUser } from '../types';

type AuthStatus = 'loading' | 'ready';

interface AuthContextValue {
  status: AuthStatus;
  requireAuth: boolean;
  isAuthenticated: boolean;
  user: AuthUser | null;
  landingPageEnabled: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
  changePassword: (currentPassword: string, newPassword: string) => Promise<void>;
  refreshUser: () => Promise<void>;
  toggleDarkMode: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

interface InternalState {
  status: AuthStatus;
  requireAuth: boolean;
  user: AuthUser | null;
  landingPageEnabled: boolean;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<InternalState>({
    status: 'loading',
    requireAuth: false,
    user: null,
    landingPageEnabled: false,
  });

  useEffect(() => {
    if (state.user?.dark_mode) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [state.user?.dark_mode]);

  const bootstrapAuth = useCallback(async () => {
    try {
      const statusResponse = await authApi.getStatus();
      const requireAuth = Boolean(statusResponse.require_auth);
      const landingPageEnabled = Boolean(statusResponse.landing_page_enabled);

      if (!requireAuth) {
        setState({
          status: 'ready',
          requireAuth: false,
          user: null,
          landingPageEnabled,
        });
        return;
      }

      try {
        const me = await authApi.getCurrentUser();
        setState({
          status: 'ready',
          requireAuth: true,
          user: me.user,
          landingPageEnabled,
        });
      } catch {
        setState({
          status: 'ready',
          requireAuth: true,
          user: null,
          landingPageEnabled,
        });
      }
    } catch (error) {
      console.error('Failed to initialize auth state', error);
      setState({
        status: 'ready',
        requireAuth: false,
        user: null,
        landingPageEnabled: false,
      });
    }
  }, []);

  useEffect(() => {
    void bootstrapAuth();
  }, [bootstrapAuth]);

  const login = useCallback(async (username: string, password: string) => {
    const trimmedUsername = username.trim();
    if (!trimmedUsername) {
      throw new Error('Username is required.');
    }

    const response = await authApi.login(trimmedUsername, password);
    setState((prev) => ({
      status: 'ready',
      requireAuth: true,
      user: response.user,
      landingPageEnabled: prev.landingPageEnabled,
    }));
  }, []);

  const logout = useCallback(() => {
    void authApi.logout().catch((error) => {
      console.warn('Failed to log out cleanly', error);
    });
    setState((prev) => ({
      status: 'ready',
      requireAuth: prev.requireAuth,
      user: prev.requireAuth ? null : prev.user,
      landingPageEnabled: prev.landingPageEnabled,
    }));
  }, []);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });
    },
    [],
  );

  const refreshUser = useCallback(async () => {
    if (!state.requireAuth) {
      return;
    }
    try {
      const me = await authApi.getCurrentUser();
      setState((prev) => ({
        ...prev,
        user: me.user,
      }));
    } catch (error) {
      console.warn('Session expired while refreshing user', error);
      setState((prev) => ({
        ...prev,
        user: null,
      }));
    }
  }, [state.requireAuth]);

  const toggleDarkMode = useCallback(async () => {
    if (!state.user) return;
    try {
      const newDarkMode = !state.user.dark_mode;
      const response = await authApi.updateSettings({ dark_mode: newDarkMode });
      setState((prev) => {
        if (!prev.user) return prev;
        return {
          ...prev,
          user: {
            ...prev.user,
            dark_mode: response.dark_mode,
          },
        };
      });
    } catch (error) {
      console.error('Failed to update dark mode setting', error);
    }
  }, [state.user]);

  const value = useMemo<AuthContextValue>(() => {
    const isAuthenticated = !state.requireAuth || Boolean(state.user);
    return {
      status: state.status,
      requireAuth: state.requireAuth,
      isAuthenticated,
      user: state.user,
      landingPageEnabled: state.landingPageEnabled,
      login,
      logout,
      changePassword,
      refreshUser,
      toggleDarkMode,
    };
  }, [changePassword, login, logout, refreshUser, state.requireAuth, state.status, state.user, toggleDarkMode]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = (): AuthContextValue => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
