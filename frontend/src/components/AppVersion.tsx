import { useEffect, useState } from 'react'

import { getHealth } from '../api/client'

let cachedVersion: string | null = null
let pendingVersion: Promise<string | null> | null = null

function loadVersion(): Promise<string | null> {
  if (cachedVersion) {
    return Promise.resolve(cachedVersion)
  }
  if (!pendingVersion) {
    pendingVersion = getHealth()
      .then((health) => {
        cachedVersion = health.version
        return health.version
      })
      .catch(() => null)
      .finally(() => {
        pendingVersion = null
      })
  }
  return pendingVersion
}

interface AppVersionProps {
  className?: string
}

/** Shows the backend version from ``GET /api/v1/health`` (S60-Fix-002). */
export default function AppVersion({ className }: AppVersionProps) {
  const [version, setVersion] = useState<string | null>(cachedVersion)

  useEffect(() => {
    let active = true
    void loadVersion().then((value) => {
      if (active) {
        setVersion(value)
      }
    })
    return () => {
      active = false
    }
  }, [])

  if (!version) {
    return null
  }
  return (
    <span className={className} title={`IIRuchating v${version}`}>
      v{version}
    </span>
  )
}
