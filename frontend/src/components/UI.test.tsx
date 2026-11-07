import {render,screen} from '@testing-library/react'
import {describe,it,expect} from 'vitest'
import {Table,Badge} from './UI'
import {allPages,slug} from '../navigation'
describe('Evidence presentation',()=>{
 it('does not present unavailable probabilities as zero',()=>{render(<Table rows={[{id:1,probability:null}]} columns={[{key:'probability',label:'Probability'}]}/>);expect(screen.getByText('—')).toBeInTheDocument()})
 it('clearly identifies draft recommendations',()=>{render(<Badge value="draft"/>);expect(screen.getByText('draft')).toBeInTheDocument()})
 it('has 52 unique navigable modules',()=>{expect(allPages).toHaveLength(52);expect(new Set(allPages.map(slug)).size).toBe(52)})
})
