import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '@/services/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingSpinner } from '@/components/common/LoadingSpinner'
import toast from 'react-hot-toast'
import { MODEL_STAGES } from '@/utils/constants'
import { useModels } from '@/features/models/hooks/useModels'
import { useModelPromotion } from '@/features/models/hooks/useModelPromotion'
import { usePaperSession } from '@/features/models/hooks/usePaperSession'
import type { ModelStage, Model } from '@/types/model'

interface PaperSession {
  id: number
  model_id: number
  status: string
  start_balance: number
  current_balance: number
  total_trades: number
  winning_trades: number
  pnl: number
  sharpe_ratio?: number
  max_drawdown?: number
  started_at: string
  ended_at?: string
}

export default function ModelRegistry() {
  const [selectedStage, setSelectedStage] = useState<ModelStage | 'all'>('all')
  const [selectedModel, setSelectedModel] = useState<Model | null>(null)

  const { filteredModels, isLoading } = useModels(selectedStage)
  const {
    promoteModelId,
    setPromoteModelId,
    promoteStage,
    setPromoteStage,
    totpCode,
    setTotpCode,
    handlePromote,
    isPending: isPromoting,
  } = useModelPromotion()

  const {
    paperSessions,
    runningSession,
    paperSessionBalance,
    setPaperSessionBalance,
    handleStartSession,
    handleStopSession,
  } = usePaperSession(selectedModel?.id || null)

  const { data: validation } = useQuery({
    queryKey: ['validation', selectedModel?.id],
    queryFn: () => api.getModelValidation(selectedModel!.id),
    enabled: !!selectedModel && selectedModel.stage === 'paper',
  })

  if (isLoading) {
    return <LoadingSpinner />
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Model Registry</h1>
        <p className="text-muted-foreground">Manage model lifecycle and promotions</p>
      </div>

      {/* Stage Filter */}
      <div className="flex gap-2">
        <Button
          variant={selectedStage === 'all' ? 'default' : 'outline'}
          onClick={() => setSelectedStage('all')}
        >
          All
        </Button>
        {Object.keys(MODEL_STAGES).map((stage) => (
          <Button
            key={stage}
            variant={selectedStage === stage ? 'default' : 'outline'}
            onClick={() => setSelectedStage(stage as ModelStage)}
          >
            {MODEL_STAGES[stage].label}
          </Button>
        ))}
      </div>

      {/* Models Table */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredModels.map((model: Model) => {
          const stageInfo = MODEL_STAGES[model.stage]
          const isSelected = selectedModel?.id === model.id
          const modelRunningSession = model.stage === 'paper' && selectedModel?.id === model.id 
            ? runningSession 
            : null
          
          return (
            <Card 
              key={model.id} 
              className={isSelected ? 'ring-2 ring-primary' : ''}
              onClick={() => setSelectedModel(model)}
            >
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">v{model.version}</CardTitle>
                  <span
                    className={`rounded-full px-2 py-1 text-xs text-white ${stageInfo.color}`}
                  >
                    {stageInfo.label}
                  </span>
                </div>
                <CardDescription>
                  Experiment #{model.experiment_id} • {new Date(model.created_at).toLocaleDateString()}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-2 text-sm">
                  {model.paper_trading_results && (
                    <div className="space-y-1">
                      <div>
                        <span className="font-medium">Sharpe:</span>{' '}
                        {model.paper_trading_results.sharpe_ratio != null ? model.paper_trading_results.sharpe_ratio.toFixed(2) : 'N/A'}
                      </div>
                      <div>
                        <span className="font-medium">Win Rate:</span>{' '}
                        {model.paper_trading_results.win_rate != null ? (model.paper_trading_results.win_rate * 100).toFixed(1) : 'N/A'}%
                      </div>
                      <div>
                        <span className="font-medium">Trades:</span>{' '}
                        {model.paper_trading_results.total_trades ?? 0}
                      </div>
                    </div>
                  )}
                  
                  {validation && model.stage === 'paper' && (
                    <div className={`p-2 rounded ${validation.passed ? 'bg-green-100' : 'bg-red-100'}`}>
                      <div className="font-medium text-xs">
                        Validation: {validation.passed ? '✓ Passed' : '✗ Failed'}
                      </div>
                    </div>
                  )}

                  {model.stage === 'paper' && modelRunningSession && (
                    <div className="p-2 rounded bg-blue-100">
                      <div className="text-xs">
                        <div className="font-medium">Session Running</div>
                        <div>Balance: ${modelRunningSession.current_balance.toFixed(2)}</div>
                        <div>Trades: {modelRunningSession.total_trades}</div>
                      </div>
                    </div>
                  )}

                  <div className="flex flex-wrap gap-2 pt-2">
                    {model.stage === 'staging' && (
                      <Button
                        size="sm"
                        onClick={(e) => {
                          e.stopPropagation()
                          setPromoteModelId(model.id)
                          setPromoteStage('paper')
                        }}
                      >
                        Promote to Paper
                      </Button>
                    )}
                    {model.stage === 'paper' && (
                      <>
                        {!modelRunningSession && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleStartSession(model.id)
                            }}
                          >
                            Start Paper Trading
                          </Button>
                        )}
                        {modelRunningSession && (
                          <Button
                            size="sm"
                            variant="outline"
                            onClick={(e) => {
                              e.stopPropagation()
                              handleStopSession(model.id, modelRunningSession.id)
                            }}
                          >
                            Stop Session
                          </Button>
                        )}
                        <Button
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation()
                            setPromoteModelId(model.id)
                            setPromoteStage('production')
                          }}
                          disabled={!validation?.passed}
                        >
                          Promote to Production
                        </Button>
                      </>
                    )}
                    {model.stage === 'production' && (
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={(e) => {
                          e.stopPropagation()
                          // TODO: Implement rollback
                          toast('Rollback feature coming soon')
                        }}
                      >
                        Rollback
                      </Button>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {/* Model Details Modal */}
      {selectedModel && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle>Model Details: v{selectedModel.version}</CardTitle>
              <Button variant="ghost" onClick={() => setSelectedModel(null)}>Close</Button>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-sm font-medium">Stage</div>
                <div>{MODEL_STAGES[selectedModel.stage].label}</div>
              </div>
              <div>
                <div className="text-sm font-medium">Experiment ID</div>
                <div>{selectedModel.experiment_id}</div>
              </div>
              <div>
                <div className="text-sm font-medium">Created</div>
                <div>{new Date(selectedModel.created_at).toLocaleString()}</div>
              </div>
              {selectedModel.promoted_at && (
                <div>
                  <div className="text-sm font-medium">Promoted</div>
                  <div>{new Date(selectedModel.promoted_at).toLocaleString()}</div>
                </div>
              )}
            </div>

            {selectedModel.paper_trading_results && (
              <div>
                <div className="text-sm font-medium mb-2">Paper Trading Results</div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>Total Trades: {selectedModel.paper_trading_results.total_trades ?? 0}</div>
                  <div>Win Rate: {selectedModel.paper_trading_results.win_rate != null ? (selectedModel.paper_trading_results.win_rate * 100).toFixed(1) : '0'}%</div>
                  <div>Sharpe Ratio: {selectedModel.paper_trading_results.sharpe_ratio != null ? selectedModel.paper_trading_results.sharpe_ratio.toFixed(2) : 'N/A'}</div>
                  <div>Max Drawdown: {selectedModel.paper_trading_results.max_drawdown != null ? (selectedModel.paper_trading_results.max_drawdown * 100).toFixed(2) : 'N/A'}%</div>
                  <div>P&L: ${selectedModel.paper_trading_results.pnl != null ? selectedModel.paper_trading_results.pnl.toFixed(2) : '0.00'}</div>
                  <div>Days Traded: {selectedModel.paper_trading_results.days_traded ?? 0}</div>
                </div>
              </div>
            )}

            {selectedModel.stage === 'paper' && paperSessions && (
              <div>
                <div className="text-sm font-medium mb-2">Paper Trading Sessions</div>
                <div className="space-y-2">
                  {paperSessions.map((session: PaperSession) => (
                    <div key={session.id} className="p-2 border rounded">
                      <div className="flex justify-between">
                        <div>
                          <div className="text-xs font-medium">Session #{session.id}</div>
                          <div className="text-xs text-muted-foreground">
                            {new Date(session.started_at).toLocaleString()}
                          </div>
                        </div>
                        <div className="text-right">
                          <div className="text-xs">{session.status}</div>
                          <div className="text-xs">${session.current_balance.toFixed(2)}</div>
                        </div>
                      </div>
                      <div className="text-xs mt-1">
                        Trades: {session.total_trades} | P&L: ${session.pnl.toFixed(2)}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {selectedModel.stage === 'paper' && validation && (
              <div>
                <div className="text-sm font-medium mb-2">Validation Status</div>
                <div className={`p-3 rounded ${validation.passed ? 'bg-green-50' : 'bg-red-50'}`}>
                  <div className="font-medium mb-2">
                    {validation.passed ? '✓ Validation Passed' : '✗ Validation Failed'}
                  </div>
                  <div className="space-y-1 text-sm">
                    {Object.entries(validation.checks).map(([check, passed]) => (
                      <div key={check} className={passed ? 'text-green-700' : 'text-red-700'}>
                        {passed ? '✓' : '✗'} {check.replace('_', ' ')}
                      </div>
                    ))}
                  </div>
                  {validation.messages.length > 0 && (
                    <div className="mt-2 text-sm text-red-700">
                      {validation.messages.map((msg: string, i: number) => (
                        <div key={i}>{msg}</div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Promotion Confirmation Modal */}
      {promoteModelId && promoteStage && (
        <Card>
          <CardHeader>
            <CardTitle>Confirm Promotion</CardTitle>
            <CardDescription>
              Promote model to {MODEL_STAGES[promoteStage].label}
              {promoteStage === 'production' && ' (requires 2FA)'}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {promoteStage === 'production' && (
              <Input
                placeholder="Enter 6-digit 2FA code"
                value={totpCode}
                onChange={(e) => setTotpCode(e.target.value)}
                maxLength={6}
              />
            )}
            {promoteStage === 'paper' && (
              <div>
                <label className="text-sm font-medium">Starting Balance</label>
                <Input
                  type="number"
                  value={paperSessionBalance}
                  onChange={(e) => setPaperSessionBalance(Number(e.target.value))}
                  min={1000}
                  step={1000}
                />
              </div>
            )}
            <div className="flex gap-2">
              <Button
                onClick={handlePromote}
                disabled={
                  isPromoting || 
                  (promoteStage === 'production' && totpCode.length !== 6)
                }
              >
                {isPromoting ? <LoadingSpinner size="sm" /> : 'Confirm'}
              </Button>
              <Button 
                variant="outline" 
                onClick={() => {
                  setPromoteModelId(null)
                  setPromoteStage(null)
                  setTotpCode('')
                }}
              >
                Cancel
              </Button>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
