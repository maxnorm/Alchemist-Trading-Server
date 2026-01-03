import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import toast from 'react-hot-toast'
import { formatRelativeTime } from '@/utils/formatters'
import { useModelAssignment } from '@/features/trading/hooks/useModelAssignment'

export default function MT5Accounts() {
  const queryClient = useQueryClient()
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
    refetchInterval: 10000,
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

  if (accountsLoading) {
    return <LoadingSpinner />
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">MT5 Accounts</h1>
        <p className="text-muted-foreground">Manage MT5 account connections and model assignments</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {accounts?.map((account) => {
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
        })}
      </div>

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
