import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import { formatCurrency, formatPercent } from '@/utils/formatters'
import { useTradingStatus } from '@/features/trading/hooks/useTradingStatus'
import { useKillSwitch } from '@/features/trading/hooks/useKillSwitch'
import { useTradingPositions } from '@/hooks/useTradingPositions'

export default function LiveTrading() {
  const { status } = useTradingStatus()
  const { positions } = useTradingPositions()
  const {
    killSwitchCode,
    setKillSwitchCode,
    showDialog,
    openDialog,
    closeDialog,
    handleTrigger,
    handleReset,
    isTriggering,
    isResetting,
  } = useKillSwitch()

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Live Trading</h1>
        <p className="text-muted-foreground">Monitor and control live trading operations</p>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Trading Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Status:</span>
                <span className={status?.is_active ? 'text-green-600' : 'text-red-600'}>
                  {status?.is_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Kill Switch:</span>
                <span className={status?.kill_switch_active ? 'text-red-600' : 'text-green-600'}>
                  {status?.kill_switch_active ? 'Active' : 'Inactive'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Active Positions:</span>
                <span>{status?.active_positions || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Total Equity:</span>
                <span>{formatCurrency(status?.total_equity || 0)}</span>
              </div>
            </div>
            <div className="flex gap-2">
              {!status?.kill_switch_active ? (
                <Button variant="destructive" onClick={openDialog}>
                  Activate Kill Switch
                </Button>
              ) : (
                <Button variant="outline" onClick={openDialog}>
                  Reset Kill Switch
                </Button>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Active Positions</CardTitle>
            <CardDescription>{positions.length} open positions</CardDescription>
          </CardHeader>
          <CardContent>
            {positions.length === 0 ? (
              <p className="text-muted-foreground">No open positions</p>
            ) : (
              <div className="space-y-2">
                {positions.map((position) => (
                  <div key={position.id} className="rounded-md border p-3 text-sm">
                    <div className="flex justify-between">
                      <span className="font-medium">{position.symbol}</span>
                      <span
                        className={
                          position.unrealized_pnl >= 0 ? 'text-green-600' : 'text-red-600'
                        }
                      >
                        {formatCurrency(position.unrealized_pnl)} (
                        {formatPercent(position.unrealized_pnl_pct)})
                      </span>
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {position.order_type} {position.volume} @ {position.entry_price}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {showDialog && (
        <Card>
          <CardHeader>
            <CardTitle>
              {status?.kill_switch_active ? 'Reset Kill Switch' : 'Activate Kill Switch'}
            </CardTitle>
            <CardDescription>Enter 2FA code to confirm</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <Input
              placeholder="Enter 6-digit code"
              value={killSwitchCode}
              onChange={(e) => setKillSwitchCode(e.target.value)}
              maxLength={6}
            />
            <div className="flex gap-2">
              <Button
                variant={status?.kill_switch_active ? 'default' : 'destructive'}
                onClick={status?.kill_switch_active ? handleReset : handleTrigger}
                disabled={
                  (status?.kill_switch_active ? isResetting : isTriggering) ||
                  killSwitchCode.length !== 6
                }
              >
                {(status?.kill_switch_active ? isResetting : isTriggering) ? (
                  <LoadingSpinner size="sm" />
                ) : (
                  'Confirm'
                )}
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
