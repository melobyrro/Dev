import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRole?: 'owner' | 'admin' | 'user';
  requireSuperadmin?: boolean;
}

/**
 * ProtectedRoute component that wraps routes requiring authentication.
 *
 * @param children - The child components to render if authorized
 * @param requiredRole - Minimum role required (owner > admin > user)
 * @param requireSuperadmin - If true, requires user to be a superadmin
 */
export function ProtectedRoute({
  children,
  requiredRole,
  requireSuperadmin = false
}: ProtectedRouteProps) {
  const { isAuthenticated, isLoading, user, role } = useAuthStore();

  // Show loading state while checking authentication
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-indigo-600"></div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Check superadmin requirement
  if (requireSuperadmin && !user?.is_superadmin) {
    return <Navigate to="/" replace />;
  }

  // Check role requirement
  if (requiredRole && role) {
    const roleHierarchy: Record<string, number> = {
      owner: 3,
      admin: 2,
      user: 1,
    };

    const userLevel = roleHierarchy[role] || 0;
    const requiredLevel = roleHierarchy[requiredRole] || 0;

    if (userLevel < requiredLevel) {
      return <Navigate to="/" replace />;
    }
  }

  return <>{children}</>;
}
