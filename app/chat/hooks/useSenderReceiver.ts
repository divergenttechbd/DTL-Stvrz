import { useAuthStore } from '~/store/authStore'
// import { Peer } from '~/queries/models/conversation'

export interface UseSenderReceiverArgs {
  fromUser: any | undefined
  toUser: any | undefined
}

export const useSenderReceiver = ({
  fromUser,
  toUser,
}: UseSenderReceiverArgs) => {
  const { userData } = useAuthStore()
  const isBlank = (!fromUser || !toUser)

  return {
    sender: isBlank ? undefined : userData?.u_type === 'host' ? toUser : fromUser,
    receiver: isBlank ? undefined : userData?.u_type === 'host' ? fromUser : toUser,
  }
}
