import {render,screen,fireEvent,waitFor,cleanup} from '@testing-library/react'
import {afterEach,describe,it,expect,vi} from 'vitest'
import {Auth} from './Auth'
import {api} from '../services/api'

vi.mock('../services/api',()=>({api:{post:vi.fn()},errorMessage:()=> 'Email already registered'}))
afterEach(()=>{cleanup();vi.unstubAllEnvs();vi.clearAllMocks();sessionStorage.clear()})
describe('Hosted account creation',()=>{
 it('offers registration and signs in after successful creation',async()=>{
  vi.stubEnv('PROD',true);vi.stubEnv('VITE_ALLOW_REGISTRATION','true')
  vi.mocked(api.post).mockResolvedValue({data:{access_token:'unit-test-token'}})
  const onLogin=vi.fn();render(<Auth onLogin={onLogin}/>)
  fireEvent.click(screen.getByRole('button',{name:'Create account'}))
  expect(screen.getByRole('heading',{name:'Create your workspace account'})).toBeInTheDocument()
  fireEvent.change(screen.getByLabelText('Email'),{target:{value:'member@example.com'}})
  fireEvent.change(screen.getByLabelText('Password'),{target:{value:'MemberTestPassword42!'}})
  fireEvent.click(screen.getByRole('button',{name:'Create account'}))
  await waitFor(()=>expect(onLogin).toHaveBeenCalledOnce())
  expect(api.post).toHaveBeenCalledWith('/auth/register',{email:'member@example.com',password:'MemberTestPassword42!'})
 })
 it('keeps hosted registration hidden when it is not configured',()=>{
  vi.stubEnv('PROD',true);vi.stubEnv('VITE_ALLOW_REGISTRATION','false')
  render(<Auth onLogin={()=>{}}/>)
  expect(screen.queryByRole('button',{name:'Create account'})).not.toBeInTheDocument()
 })
})
