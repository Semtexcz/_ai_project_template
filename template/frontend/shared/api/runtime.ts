import { client } from './generated/client.gen'

export function configureApiClient(baseUrl: string) {
  client.setConfig({ baseUrl })
}
