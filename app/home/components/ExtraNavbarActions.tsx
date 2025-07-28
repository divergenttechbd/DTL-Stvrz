'use client'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useState } from 'react'
import { getToken } from '~/lib/storage/token'
import Avatar from '~/public/images/avatar.svg'
import { AuthStore, useAuthStore } from '~/store/authStore'


export const ExtraNavbarActions = () => {
  const router = useRouter()
  const { isAuthenticated, logOut, userData } = useAuthStore()
  const { u_type: user_type } = userData || {}
  const token = getToken()
  const handleSetActiveDropdown = useCallback((status?: AuthStore['authFlow']) => {
    useAuthStore.setState({ authFlow: status })
  }, [])

  const [messageCount, setMessageCount] = useState(
    userData?.unread_message_count
  )

  useEffect(() => {
    if(userData)
      setMessageCount(userData?.unread_message_count)
  }, [userData])

  useEffect(() => {
    let ws = new WebSocket(`${process.env.NEXT_PUBLIC_CHAT_SESSION_API_URL}/ws/chat/user/chat-stat/?token=${token}`) //API Guest Message Inbox Count

    ws.onmessage = (ev: MessageEvent<any>) => {
      const data = JSON.parse(ev.data)
      setMessageCount(data?.count)
    }
  }, [])


  const handleRouting = useCallback((pathName: string) => () => {
    if (isAuthenticated || pathName === '/') {
      router.push(pathName)
    } else {
      useAuthStore.setState({ authFlow: 'LOG_IN' })
    }
  }, [isAuthenticated, router])

  const handleUserLogin = useCallback(() => {
    handleSetActiveDropdown('LOG_IN')
  }, [handleSetActiveDropdown])

  const handleUserSignUp = useCallback(() => {
    handleSetActiveDropdown('SIGN_UP')
  }, [handleSetActiveDropdown])

  const handleSwitchToHost = () => {
    useAuthStore.setState({authFlow: 'HOST_LOG_IN'})
  }


  return (
    <>
      {isAuthenticated &&
        <div
          onClick={handleSwitchToHost}
          className='hidden md:block text-sm font-medium py-3 px-5 rounded-full hover:bg-neutral-100 transition cursor-pointer'
        >
          Switch to Host
        </div>  
        
      }
      {!isAuthenticated && 
      <div className='hidden md:flex'> 
        <ul className='flex justify-end items-center gap-[10px]'>
          <li className='flex justify-center items-center'>
            <button onClick={handleUserLogin} className='flex justify-center items-center gap-[10px] px-[10px] py-[6px] border border-solid border-[#FDCDBE] rounded-[8px]'>
              <div className='px-[8px] py-[7px] rounded-[30px]' style={{background:' linear-gradient(182.07deg, rgba(241, 89, 39, 0) -68.03%, rgba(241, 89, 39, 0.46772) -13.86%, #F15927 98.26%)'}}>
                <Image src={Avatar} alt='login avatar ' width={12} height={15} className='max-w-[12px] h-auto'/>  
              </div>
              <div className='text-[#202020] text-sm font-medium'>Login</div>
            </button>
          </li>
          <li className='flex justify-center items-center'>
            <button onClick={handleUserSignUp} className='flex justify-center items-center gap-[10px] px-[20px] py-[11px] rounded-[8px] bg-[#F15927]'>
              <div className='text-[#ffffff] text-sm font-medium'>Sign Up</div>
            </button>
          </li>
        </ul>
      </div>}
    </>
  )
}
