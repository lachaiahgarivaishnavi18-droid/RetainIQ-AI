import {render,screen} from '@testing-library/react'
import {describe,it,expect} from 'vitest'
import {DeploymentSetup} from './DeploymentSetup'
describe('Unconnected production deployment',()=>{
 it('shows honest backend status and a working guide link',()=>{render(<DeploymentSetup/>);expect(screen.getByText('Awaiting connection')).toBeInTheDocument();expect(screen.getByRole('link',{name:/Open deployment guide/})).toHaveAttribute('href','/deployment-guide.html');expect(screen.queryByRole('button',{name:'Sign in'})).not.toBeInTheDocument()})
})
