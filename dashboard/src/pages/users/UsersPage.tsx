import { useEffect, useState, useCallback } from 'react';
import { motion } from 'framer-motion';
import { apiClient } from '@/api/client';
import { PageTransition } from '@/components/motion';

interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  active: boolean;
  last_login?: string;
  created_at?: string;
}

export default function UsersPage() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [addForm, setAddForm] = useState({ email: '', password: '', full_name: '', role: 'viewer' });
  const [submitting, setSubmitting] = useState(false);

  const fetchUsers = useCallback(async () => {
    try {
      setError(null);
      const resp = await apiClient.get('/api/v1/users');
      setUsers(resp.data);
    } catch (err: any) {
      setError('Failed to load users');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleAddUser = async () => {
    if (!addForm.email || !addForm.password || !addForm.full_name) return;
    setSubmitting(true);
    try {
      await apiClient.post('/api/v1/users', addForm);
      setShowAddForm(false);
      setAddForm({ email: '', password: '', full_name: '', role: 'viewer' });
      fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to create user');
    } finally {
      setSubmitting(false);
    }
  };

  const handleUpdateRole = async (userId: string, newRole: string) => {
    try {
      await apiClient.patch(`/api/v1/users/${userId}`, { role: newRole });
      fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update role');
    }
  };

  const handleToggleActive = async (userId: string, active: boolean) => {
    try {
      await apiClient.patch(`/api/v1/users/${userId}`, { active });
      fetchUsers();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update user');
    }
  };

  const formatDate = (iso?: string) => {
    if (!iso) return '—';
    return new Date(iso).toLocaleDateString('en-ZA', { day: 'numeric', month: 'short', year: 'numeric' });
  };

  const activeCount = users.filter(u => u.active).length;

  return (
    <PageTransition className="p-6 h-full overflow-y-auto bg-gray-50 dark:bg-gray-900">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Users</h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {users.length} total — {activeCount} active
          </p>
        </div>
        <button
          onClick={() => setShowAddForm(true)}
          className="px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 transition-colors"
        >
          + Invite User
        </button>
      </div>

      {/* Loading / Error */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin w-8 h-8 border-4 border-brand-600 border-t-transparent rounded-full"></div>
        </div>
      )}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 mb-4">
          <p className="text-red-700 dark:text-red-300">{error}</p>
          <button onClick={fetchUsers} className="text-sm text-red-600 underline mt-1">Retry</button>
        </div>
      )}

      {/* Users Table */}
      {!loading && !error && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead className="bg-gray-50 dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                <tr>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">User</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Email</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Role</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Status</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Last Login</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-gray-600 dark:text-gray-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {users.map((user, i) => (
                  <motion.tr
                    key={user.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.03, duration: 0.2 }}
                    className="hover:bg-gray-50 dark:hover:bg-gray-750"
                  >
                    <td className="px-4 py-3">
                      <span className="font-medium text-gray-900 dark:text-white">{user.full_name}</span>
                    </td>
                    <td className="px-4 py-3 text-gray-600 dark:text-gray-400 text-sm">{user.email}</td>
                    <td className="px-4 py-3">
                      <select
                        value={user.role}
                        onChange={(e) => handleUpdateRole(user.id, e.target.value)}
                        className="text-xs px-2 py-1 rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
                        aria-label={`Role for ${user.full_name}`}
                      >
                        <option value="admin">Admin</option>
                        <option value="farm_owner">Farm Owner</option>
                        <option value="herdsman">Herdsman</option>
                        <option value="viewer">Viewer</option>
                      </select>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 text-xs rounded-full font-medium ${user.active ? 'bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-300' : 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-300'}`}>
                        {user.active ? 'Active' : 'Disabled'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-500 dark:text-gray-400">
                      {formatDate(user.last_login)}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleToggleActive(user.id, !user.active)}
                        className={`text-xs px-3 py-1 rounded-lg ${user.active ? 'bg-red-50 text-red-600 dark:bg-red-900/30 dark:text-red-400' : 'bg-green-50 text-green-600 dark:bg-green-900/30 dark:text-green-400'}`}
                      >
                        {user.active ? 'Disable' : 'Enable'}
                      </button>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Add User Modal */}
      {showAddForm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAddForm(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-xl max-w-md w-full mx-4" onClick={e => e.stopPropagation()}>
            <div className="bg-brand-600 text-white px-6 py-4 rounded-t-xl">
              <h2 className="text-lg font-semibold">Invite New User</h2>
              <p className="text-brand-200 text-sm">Add a team member to your organisation</p>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Full Name *</label>
                <input type="text" value={addForm.full_name} onChange={e => setAddForm(f => ({...f, full_name: e.target.value}))} placeholder="e.g. Sipho Ndlovu" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Email *</label>
                <input type="email" value={addForm.email} onChange={e => setAddForm(f => ({...f, email: e.target.value}))} placeholder="sipho@farm.co.za" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Password *</label>
                <input type="password" value={addForm.password} onChange={e => setAddForm(f => ({...f, password: e.target.value}))} placeholder="Minimum 8 characters" className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Role</label>
                <select value={addForm.role} onChange={e => setAddForm(f => ({...f, role: e.target.value}))} className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100">
                  <option value="viewer">Viewer (read-only)</option>
                  <option value="herdsman">Herdsman (BLE scanning)</option>
                  <option value="farm_owner">Farm Owner (full control)</option>
                  <option value="admin">Admin (organisation-wide)</option>
                </select>
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setShowAddForm(false)} className="px-4 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg">Cancel</button>
                <button onClick={handleAddUser} disabled={!addForm.email || !addForm.password || !addForm.full_name || submitting} className="px-4 py-2 text-sm bg-brand-600 text-white rounded-lg hover:bg-brand-700 disabled:opacity-50">
                  {submitting ? 'Creating...' : 'Create User'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </PageTransition>
  );
}
