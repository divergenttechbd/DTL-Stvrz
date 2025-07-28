import Image from 'next/image'
import { FC, useEffect, useState } from 'react'
import { getToken } from '~/lib/storage/token'
import { useAuthStore } from '~/store/authStore'

type DropdownTogglerProps = {
  onToggle: React.MouseEventHandler<HTMLButtonElement>;
}
export const DropdownToggler:FC<DropdownTogglerProps> = ({ onToggle }) => {
  const { userData } = useAuthStore()
  const { userFirstLetter, image } = userData || {}
  const token = getToken()
  const [messageCount, setMessageCount] = useState(
    userData?.unread_message_count
  )

  useEffect(() => {
    let ws = new WebSocket(`${process.env.NEXT_PUBLIC_CHAT_SESSION_API_URL}/ws/chat/user/chat-stat/?token=${token}`) //API Guest Message Inbox Count

    ws.onmessage = (ev: MessageEvent<any>) => {
      const data = JSON.parse(ev.data)
      setMessageCount(data?.count)
    }
  }, [])

  return (
    <button className='flex text-sm p-1 border-grayBorder border rounded-full' type='button' onClick={onToggle}>
      <span className='sr-only'>Open user menu</span>
      <div className='rounded-full h-8 w-8 bg-gray-300 flex items-center justify-center relative'>
        {(messageCount && messageCount > 0) ? (
          <div className='absolute z-[1] -top-3 -right-2 flex justify-center items-center bg-[#f66c0e] w-4 h-4 rounded-full text-[#ffffff] text-[0.45rem]'>{messageCount}</div>
        ): <></>}
        {
          image ? (
            <Image
              src={image}
              alt='profile-image'
              fill
              className='rounded-full relative object-cover'
            />
          ) : (<span className='text-sm text-white'>{userFirstLetter}</span>)
        }
      </div>
    </button>
  )
}
