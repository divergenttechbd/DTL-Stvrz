'use client'

import { useRouter } from 'next/navigation'
import { FC, useCallback, useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSignInFormMeta } from '~/app/auth/hooks/meta/useSignInFormMeta'
import Form from '~/components/form/Form'
import Button from '~/components/layout/Button'
import { saveToken } from '~/lib/storage/token'
import { login } from '~/queries/client/auth'
import { useAuthStore } from '~/store/authStore'
import Cookie from 'js-cookie'

type SignInFormType = {
  onSuccess: Function
  handleSwitch: Function
  authFlow: string
}
const SignInForm: FC<SignInFormType> = ({ onSuccess, handleSwitch, authFlow }) => {
  const [loading, setLoading] = useState(false)
  const formInstance = useForm()
  const router = useRouter()
  const { getUserData, setIsAuthenticated } = useAuthStore()
  const [signInFields] = useSignInFormMeta(authFlow === 'GUEST_LOG_IN' || authFlow === 'HOST_LOG_IN')
  const submitButtonText = authFlow === 'GUEST_LOG_IN' ? 'Login as Guest' : authFlow === 'HOST_LOG_IN' ? 'Login as Host' : 'Continue'

  useEffect(() => {
    formInstance.setValue('userRole', authFlow === 'GUEST_LOG_IN' ? ['guest'] : authFlow === 'HOST_LOG_IN' ? ['host'] : [])
  }, [authFlow, formInstance])

  const handleSubmit = useCallback(
    async (formData: any) => {
      try {
        setLoading(true)
        const payload = {
          phoneNumber: formData.phoneNumber,
          password: formData.password,
          userRole: formData?.userRole?.[0] || 'guest',
        }
        const res = await login(payload)
        if(!res?.isSucceed) {
          throw res
        }
        saveToken({
          access_token: res.data.access_token,
          refresh_token: res.data.refresh_token,
          cookie_token: 'bearer ' + res.data.access_token,
          user_type: formData?.userRole[0]
        })
        setIsAuthenticated(true)
        const userData = await getUserData()
        setLoading(false)
        onSuccess(null, {
          userFullName: userData?.full_name,
          phoneNumber: userData?.phone_number,
          userRole: userData?.u_type,
        })
        Cookie.set('host_guest_user_id', userData?.id ?? '', { expires: 90, path: '/' })
        if((window as any).flutterChannel) {
          (window as any).flutterChannel.postMessage('successLogin')
        }
        return res
      } catch(error: any) {
        setLoading(false)
        return error
      }
    },
    [onSuccess, getUserData, setIsAuthenticated]
  )

  const handleSwitchSignUpForm = useCallback(() => {
    handleSwitch('SIGN_UP')
  }, [handleSwitch])

  const handleSwitchForgotPassForm = useCallback(() => {
    handleSwitch('FORGET_PASSWORD_FORM')
  }, [handleSwitch])

  return (
    <div className=''>
      <Form
        formInstance={formInstance}
        fields={signInFields}
        submitButtonLabel={
          <Button
            label={submitButtonText}
            loadingText={submitButtonText}
            variant='regular'
            type='submit'
            loading={loading}
          />
        }
        onSubmit={handleSubmit}
        footerContent={
          <div className='flex justify-end sm:mb-[40px]'>
            <button
              type='button'
              className='bg-transparent border-none text-[#202020] text-[12px] font-medium leading-[15px] text-right leading-2'
              onClick={handleSwitchForgotPassForm}
            >
              Forgot Password
            </button>
          </div>
        }
        resetForm={false}
      />
      <div className='mt-[10px] text-center text-[14px] font-[500] leading-[24px] text-[#1F2C37]'>
        Don&apos;t have an account?{' '}
        <button
          className='text-[#194CC3] underline underline-offset-1'
          onClick={handleSwitchSignUpForm}
        >
          Sign Up
        </button>
      </div>
    </div>
  )
}

export default SignInForm
