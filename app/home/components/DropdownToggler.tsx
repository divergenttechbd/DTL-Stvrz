'use client'

import { List } from '@phosphor-icons/react'
import Image from 'next/image'
import React, { useEffect, useState } from 'react'
import Avatar from '~/components/Images/Avatar'
import { getToken } from '~/lib/storage/token'
import { useAuthStore } from '~/store/authStore'

type DropdownTogglerProps = {
  onToggle: React.MouseEventHandler<HTMLButtonElement>;
}
export const DropdownToggler = ({ onToggle }: DropdownTogglerProps) => {
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
    <button className='flex items-center gap-x-[15px] border-[1px] border-solid border-[#DDDDDD] rounded-[21px] text-sm p-[5px] ' type='button' onClick={onToggle}>
      <span className='sr-only'>Open user menu</span>
      <List size={20} />
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
          ) : userFirstLetter ? (
            <span className='text-sm text-white'>{userFirstLetter}</span>
          ) : <Avatar />
        }
        
      </div>
    </button>
  )
}
