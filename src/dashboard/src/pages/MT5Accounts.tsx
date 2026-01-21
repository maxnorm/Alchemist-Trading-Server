import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import toast from 'react-hot-toast'
import { formatRelativeTime, formatCurrency } from '@/utils/formatters'
import { useModelAssignment } from '@/features/trading/hooks/useModelAssignment'
import { PageHeader } from '@/components/common/PageHeader'
import { HealthDot } from '@/components/common/StatusBadge'
import { RefreshCw, Plus, Copy, X } from 'lucide-react'
import type { AccountType } from '@/types/mt5'

export default function MT5Accounts() {
  const queryClient = useQueryClient()
  const [showRegister, setShowRegister] = useState(false)
  const [registerForm, setRegisterForm] = useState<{
    account_login: string
    account_name: string
    account_type: AccountType
    mt5_password: string
    mt5_server: string
  }>({
    account_login: '',
    account_name: '',
    account_type: 'live',
    mt5_password: '',
    mt5_server: '',
  })
  const {
    assignAccountId,
    assignModelId,
    setAssignModelId,
    totpCode,
    setTotpCode,
    showDialog,
    openAssignmentDialog,
    closeDialog,
    handleAssign,
    isPending: isAssigning,
  } = useModelAssignment()

  const { data: accounts, isLoading: accountsLoading } = useQuery({
    queryKey: ['mt5-accounts'],
    queryFn: () => api.getMT5Accounts(),
    // Only refetch in background if data is stale (respects global staleTime: 30s)
    // Remove aggressive refetchInterval - let React Query handle caching
    refetchInterval: false,
    // Refetch when window regains focus to keep data fresh
    refetchOnWindowFocus: true,
  })

  const { data: models } = useQuery({
    queryKey: ['models'],
    queryFn: () => api.getModels(),
  })

  const pauseMutation = useMutation({
    mutationFn: (accountId: number) => api.pauseTrading(accountId),
    onSuccess: () => {
      toast.success('Trading paused')
      queryClient.invalidateQueries({ queryKey: ['mt5-accounts'] })
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to pause trading')
    },
  })

  const [showAuthToken, setShowAuthToken] = useState<string | null>(null)

  const registerMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        account_login: Number(registerForm.account_login),
        account_type: registerForm.account_type,
        account_name: registerForm.account_name || undefined,
        mt5_password: registerForm.mt5_password || undefined,
        mt5_server: registerForm.mt5_server || undefined,
      }
      return api.postMt5AccountRegister(payload)
    },
    onSuccess: (data) => {
      // Show auth_token if available (for ZeroMQ connection)
      if (data.auth_token) {
        setShowAuthToken(data.auth_token)
        toast.success('MT5 account registered! Auth token available below.', { duration: 5000 })
      } else {
        toast.success('MT5 account registered successfully')
      }
      // Reset form
      setRegisterForm({
        account_login: '',
        account_name: '',
        account_type: 'live',
        mt5_password: '',
        mt5_server: '',
      })
      setShowRegister(false)
      queryClient.invalidateQueries({ queryKey: ['mt5-accounts'] })
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Failed to register MT5 account')
    },
  })

  const handleRegisterSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!registerForm.account_login) {
      toast.error('Account login is required')
      return
    }
    // Password and server are optional (for ZeroMQ connection)
    // But if one is provided, both must be provided (for Python API)
    if (registerForm.mt5_password && !registerForm.mt5_server) {
      toast.error('MT5 server is required when password is provided (for Python API connection)')
      return
    }
    if (registerForm.mt5_server && !registerForm.mt5_password) {
      toast.error('MT5 password is required when server is provided (for Python API connection)')
      return
    }
    registerMutation.mutate()
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: ['mt5-accounts'] })
    queryClient.invalidateQueries({ queryKey: ['models'] })
    toast.success('Accounts refreshed')
  }

  const connectedCount = accounts?.filter((acc) => {
    // Use connection_status from API, which is based on actual MT5Connection records
    return acc.connection_status === 'connected'
  }).length || 0

  return (
    <div className="space-y-6">
      <PageHeader
        title="MT5 Accounts"
        description="Manage account connections, model assignments, and trading controls"
        actions={
          <div className="flex items-center gap-3">
            <Button
              variant="outline"
              size="sm"
              onClick={handleRefresh}
              disabled={accountsLoading}
              className="gap-2"
            >
              <RefreshCw className={`h-4 w-4 ${accountsLoading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
            <Button
              variant="default"
              size="sm"
              onClick={() => setShowRegister((v) => !v)}
              className="gap-2"
            >
              <Plus className="h-4 w-4" />
              {showRegister ? 'Hide' : 'Register Account'}
            </Button>
            <HealthDot 
              status={connectedCount > 0 ? 'ok' : accounts && accounts.length > 0 ? 'warn' : 'error'} 
              label={`${connectedCount}/${accounts?.length || 0} connected`}
            />
          </div>
        }
      />

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Register MT5 Account</CardTitle>
            <CardDescription>Register a new MT5 account for Python API trading (no EA required)</CardDescription>
          </div>
        </CardHeader>
        {showRegister && (
          <CardContent className="space-y-4">
            <form className="space-y-4" onSubmit={handleRegisterSubmit}>
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <label className="block text-sm font-medium mb-1">Account login</label>
                  <Input
                    value={registerForm.account_login}
                    onChange={(e) =>
                      setRegisterForm((f) => ({ ...f, account_login: e.target.value }))
                    }
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Account name</label>
                  <Input
                    value={registerForm.account_name}
                    onChange={(e) =>
                      setRegisterForm((f) => ({ ...f, account_name: e.target.value }))
                    }
                    placeholder="Optional, for display in dashboard"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">Account type</label>
                  <select
                    className="w-full rounded-md border border-input bg-background pl-3 pr-8 py-2"
                    value={registerForm.account_type}
                    onChange={(e) =>
                      setRegisterForm((f) => ({
                        ...f,
                        account_type: e.target.value as AccountType,
                      }))
                    }
                  >
                    <option value="live">Live</option>
                    <option value="demo">Demo</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    MT5 Password <span className="text-gray-400 text-xs">(Optional - for Python API)</span>
                  </label>
                  <Input
                    type="password"
                    value={registerForm.mt5_password}
                    onChange={(e) =>
                      setRegisterForm((f) => ({ ...f, mt5_password: e.target.value }))
                    }
                    placeholder="Leave empty for ZeroMQ connection"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Required only for Python API connection. Leave empty to use ZeroMQ (EA will need auth token).
                  </p>
                </div>
                <div>
                  <label className="block text-sm font-medium mb-1">
                    MT5 Server <span className="text-gray-400 text-xs">(Optional - for Python API)</span>
                  </label>
                  <Input
                    value={registerForm.mt5_server}
                    onChange={(e) =>
                      setRegisterForm((f) => ({ ...f, mt5_server: e.target.value }))
                    }
                    placeholder="e.g., ICMarkets-Demo, FXCM-Demo (leave empty for ZeroMQ)"
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Required only for Python API connection. Leave empty to use ZeroMQ (EA will need auth token).
                  </p>
                </div>
              </div>
              <Button type="submit" disabled={registerMutation.isPending}>
                {registerMutation.isPending ? <LoadingSpinner size="sm" /> : 'Register Account'}
              </Button>
            </form>
          </CardContent>
        )}
      </Card>

      {/* Auth Token Modal */}
      {showAuthToken && (
        <Card className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
          <CardContent className="bg-white p-6 rounded-lg shadow-lg max-w-md w-full mx-4">
            <div className="flex justify-between items-center mb-6 pt-2">
              <CardTitle className="text-gray-900">ZeroMQ Auth Token</CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAuthToken(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Use this token in your MT5 EA's <code className="bg-gray-100 px-1 rounded">auth_token</code> input parameter.
            </p>
            <div className="bg-gray-100 p-3 rounded mb-4 font-mono text-sm break-all text-gray-900">
              {showAuthToken}
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => {
                  navigator.clipboard.writeText(showAuthToken)
                  toast.success('Token copied to clipboard')
                }}
                className="flex-1"
              >
                <Copy className="h-4 w-4 mr-2" />
                Copy Token
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowAuthToken(null)}
              >
                Close
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {accountsLoading && !accounts ? (
        <LoadingSpinner />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {accounts && accounts.length > 0 ? (
            accounts.map((account) => {
              const isConnected = account.connection_status === 'connected'

              return (
                <Card key={account.id}>
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg">
                        {account.account_name || `Account ${account.account_login}`}
                      </CardTitle>
                      <span
                        className={`h-2 w-2 rounded-full ${
                          isConnected ? 'bg-green-500' : 'bg-gray-400'
                        }`}
                      />
                    </div>
                    <CardDescription>
                      {account.account_login} ({account.account_type})
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    {/* Financial Information */}
                    {(account.balance !== undefined || account.equity !== undefined || account.profit !== undefined) && (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                          Financials
                        </div>
                        <div className="space-y-1.5 text-sm">
                          {account.balance !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Balance:</span>
                              <span className="font-medium">
                                {formatCurrency(account.balance, account.account_currency || 'USD')}
                              </span>
                            </div>
                          )}
                          {account.equity !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Equity:</span>
                              <span className="font-medium">
                                {formatCurrency(account.equity, account.account_currency || 'USD')}
                              </span>
                            </div>
                          )}
                          {account.profit !== undefined && (
                            <div className="flex justify-between">
                              <span className="text-muted-foreground">Profit/Loss:</span>
                              <span className={`font-medium ${account.profit >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                                {formatCurrency(account.profit, account.account_currency || 'USD')}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Account Information */}
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        Account Details
                      </div>
                      <div className="space-y-1.5 text-sm">
                        {account.broker_name && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Broker:</span>
                            <span className="font-medium">{account.broker_name}</span>
                          </div>
                        )}
                        {account.broker_server && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Server:</span>
                            <span className="font-medium">{account.broker_server}</span>
                          </div>
                        )}
                        {account.account_currency && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Currency:</span>
                            <span className="font-medium">{account.account_currency}</span>
                          </div>
                        )}
                        {account.account_leverage && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Leverage:</span>
                            <span className="font-medium">1:{account.account_leverage}</span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Connection Information */}
                    <div className="space-y-2">
                      <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                        Connection
                      </div>
                      <div className="space-y-1.5 text-sm">
                        <div className="flex justify-between">
                          <span className="text-muted-foreground">Status:</span>
                          <span className={`font-medium ${isConnected ? 'text-green-500' : 'text-gray-400'}`}>
                            {isConnected ? 'Connected' : 'Disconnected'}
                          </span>
                        </div>
                        {account.ea_version && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">EA Version:</span>
                            <span className="font-medium">{account.ea_version}</span>
                          </div>
                        )}
                        {account.connected_at && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Connected:</span>
                            <span className="text-xs text-muted-foreground">
                              {formatRelativeTime(account.connected_at)}
                            </span>
                          </div>
                        )}
                        {account.last_seen_at && (
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Last Seen:</span>
                            <span className="text-xs text-muted-foreground">
                              {formatRelativeTime(account.last_seen_at)}
                            </span>
                          </div>
                        )}
                      </div>
                    </div>

                    {/* Model Assignment */}
                    {account.current_model_id && (
                      <div className="space-y-2">
                        <div className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                          Model Assignment
                        </div>
                        <div className="space-y-1.5 text-sm">
                          <div className="flex justify-between">
                            <span className="text-muted-foreground">Model:</span>
                            <span className="font-medium">
                              {account.current_model_version || `ID: ${account.current_model_id}`}
                            </span>
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Actions */}
                    <div className="flex gap-2 pt-2 border-t">
                      <Button size="sm" variant="outline" onClick={() => openAssignmentDialog(account.id)}>
                        {account.current_model_id ? 'Change Model' : 'Assign Model'}
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => pauseMutation.mutate(account.id)}
                        disabled={pauseMutation.isPending}
                      >
                        Pause
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              )
            })
          ) : (
            <Card className="col-span-full">
              <CardContent className="py-8 text-center">
                <p className="text-muted-foreground">No MT5 accounts found</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {showDialog && assignAccountId && (
        <Card>
          <CardHeader>
            <CardTitle>Assign Model</CardTitle>
            <CardDescription>Select a model and enter 2FA code</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <select
              className="w-full rounded-md border border-input bg-background pl-3 pr-8 py-2"
              value={assignModelId || ''}
              onChange={(e) => setAssignModelId(Number(e.target.value) || null)}
            >
              <option value="">Select a model...</option>
              {models?.map((model) => (
                <option key={model.id} value={model.id}>
                  {model.name} ({model.stage})
                </option>
              ))}
            </select>
            <Input
              placeholder="Enter 6-digit 2FA code"
              value={totpCode}
              onChange={(e) => setTotpCode(e.target.value)}
              maxLength={6}
            />
            <div className="flex gap-2">
              <Button
                onClick={handleAssign}
                disabled={isAssigning || !assignModelId || totpCode.length !== 6}
              >
                {isAssigning ? <LoadingSpinner size="sm" /> : 'Assign'}
              </Button>
              <Button variant="outline" onClick={closeDialog}>
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
