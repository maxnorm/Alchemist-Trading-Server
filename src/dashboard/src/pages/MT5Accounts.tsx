import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import toast from 'react-hot-toast'
import { formatRelativeTime } from '@/utils/formatters'
import { useModelAssignment } from '@/features/trading/hooks/useModelAssignment'
import type { AccountType } from '@/types/mt5'

export default function MT5Accounts() {
  const queryClient = useQueryClient()
  const [showRegister, setShowRegister] = useState(false)
  const [registerForm, setRegisterForm] = useState<{
    account_login: string
    account_name: string
    account_type: AccountType
  }>({
    account_login: '',
    account_name: '',
    account_type: 'live',
  })
  const [registrationResult, setRegistrationResult] = useState<{
    account_login: number
    account_type: string
    auth_token: string
    server_host?: string
    server_port?: number
  } | null>(null)
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

  const registerMutation = useMutation({
    mutationFn: async () => {
      const payload = {
        account_login: Number(registerForm.account_login),
        account_type: registerForm.account_type,
        account_name: registerForm.account_name || undefined,
      }
      return api.postMt5AccountRegister(payload)
    },
    onSuccess: (data) => {
      toast.success('MT5 account registered')
      setRegistrationResult({
        account_login: data.account_login,
        account_type: data.account_type,
        auth_token: data.auth_token,
        server_host: data.server_host,
        server_port: data.server_port,
      })
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
    registerMutation.mutate()
  }

  const eaConfigSnippet =
    registrationResult &&
    `ip = ${registrationResult.server_host || 'YOUR_MT5_SERVER_HOST'}
port = ${registrationResult.server_port || 1234}
auth_token = ${registrationResult.auth_token}`

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">MT5 Accounts</h1>
        <p className="text-muted-foreground">Manage account connections and model assignments</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Register MT5 Account</CardTitle>
              <CardDescription>Generate connection details for a new MT5 account</CardDescription>
            </div>
            <Button variant="outline" onClick={() => setShowRegister((v) => !v)}>
              {showRegister ? 'Hide' : 'Register Account'}
            </Button>
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
                    className="w-full rounded-md border border-input bg-background px-3 py-2"
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
              </div>
              <Button type="submit" disabled={registerMutation.isPending}>
                {registerMutation.isPending ? <LoadingSpinner size="sm" /> : 'Generate EA token'}
              </Button>
            </form>

            {registrationResult && (
              <div className="mt-4 space-y-2">
                <h3 className="text-sm font-semibold">EA configuration</h3>
                <p className="text-xs text-muted-foreground">
                  Use these values as inputs in both <code>mt5_trading_operation.mq5</code> and{' '}
                  <code>mt5_tick_streamer.mq5</code>.
                </p>
                <pre className="whitespace-pre-wrap rounded-md bg-muted p-3 text-xs">
{eaConfigSnippet}
                </pre>
              </div>
            )}
          </CardContent>
        )}
      </Card>

      {accountsLoading && !accounts ? (
        <LoadingSpinner />
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {accounts && accounts.length > 0 ? (
            accounts.map((account) => {
              const isConnected = account.last_seen_at
                ? new Date(account.last_seen_at).getTime() > Date.now() - 60000
                : false

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
                <div className="space-y-1 text-sm">
                  <div>
                    <span className="font-medium">Broker:</span> {account.broker_name || 'N/A'}
                  </div>
                  <div>
                    <span className="font-medium">Status:</span>{' '}
                    {isConnected ? 'Connected' : 'Disconnected'}
                  </div>
                  {account.last_seen_at && (
                    <div className="text-xs text-muted-foreground">
                      {formatRelativeTime(account.last_seen_at)}
                    </div>
                  )}
                </div>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => openAssignmentDialog(account.id)}>
                    Assign Model
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
              className="w-full rounded-md border border-input bg-background px-3 py-2"
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
